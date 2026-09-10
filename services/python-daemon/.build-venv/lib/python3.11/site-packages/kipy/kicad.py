# Copyright The KiCad Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Classes for interacting with KiCad at a high level"""

import os
import platform
import random
import string
from tempfile import gettempdir
from typing import Optional, Sequence, Union
from google.protobuf.empty_pb2 import Empty

from kipy.board import Board
from kipy.client import KiCadClient, ApiError
from kipy.common_types import Text, TextBox, CompoundShape
from kipy.errors import FutureVersionError
from kipy.geometry import Box2
from kipy.project import Project
from kipy.proto.common import commands
from kipy.proto.common.types import base_types_pb2, DocumentType, DocumentSpecifier
from kipy.proto.common.commands import base_commands_pb2
from kipy.kicad_api_version import KICAD_API_VERSION


def _default_socket_path() -> str:
    path = os.environ.get('KICAD_API_SOCKET')
    if path is not None:
        return path
    if platform.system() == 'Windows':
        return f'ipc://{gettempdir()}\\kicad\\api.sock'
    else:
        # Check for default socket path of KiCad flatpak on flathub
        home = os.environ.get('HOME')
        if home is not None:
            flatpak_socket_path = f'{home}/.var/app/org.kicad.KiCad/cache/tmp/kicad/api.sock'
            if os.path.exists(flatpak_socket_path):
                return f'ipc://{flatpak_socket_path}'

        return 'ipc:///tmp/kicad/api.sock'

def _random_client_name() -> str:
    return 'anonymous-'+''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def _default_kicad_token() -> str:
    token = os.environ.get('KICAD_API_TOKEN')
    if token is not None:
        return token
    return ""

class KiCadVersion:
    def __init__(self, major: int, minor: int, patch: int, full_version: str):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.full_version = full_version

    @staticmethod
    def from_proto(proto: base_types_pb2.KiCadVersion) -> 'KiCadVersion':
        return KiCadVersion(proto.major, proto.minor, proto.patch, proto.full_version)

    @staticmethod
    def from_git_describe(describe: str) -> 'KiCadVersion':
        parts = describe.split('-')
        version_part = parts[0]

        try:
            major, minor, patch = map(int, version_part.split('.'))
        except ValueError:
            return KiCadVersion(0, 0, 0, describe)

        if len(parts) > 1:
            additional_info = '-'.join(parts[1:])
            return KiCadVersion(major, minor, patch, f"{version_part}-{additional_info}")

        return KiCadVersion(major, minor, patch, f"{version_part}")

    def __repr__(self):
        return f"{self.major}.{self.minor}.{self.patch} ({self.full_version})"

    def __eq__(self, other):
        if not isinstance(other, KiCadVersion):
            return NotImplemented

        return (
            (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
            )

    def __lt__(self, other):
        if not isinstance(other, KiCadVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other

class KiCad:
    def __init__(self, socket_path: Optional[str]=None,
                 client_name: Optional[str]=None,
                 kicad_token: Optional[str]=None,
                 timeout_ms: int=2000):
        """Creates a connection to a running KiCad instance

        :param socket_path: The path to the IPC API socket (leave default to read from the
            KICAD_API_SOCKET environment variable, which will be set automatically by KiCad when
            launching API plugins, or to use the default platform-dependent socket path if the
            environment variable is not set).
        :param client_name: A unique name identifying this plugin instance.  Leave default to
            generate a random client name.
        :param kicad_token: A token that can be provided to the client to uniquely identify a
            KiCad instance.  Leave default to read from the KICAD_API_TOKEN environment variable.
        :param timeout_ms: The maximum time to wait for a response from KiCad, in milliseconds
        """
        if socket_path is None:
            socket_path = _default_socket_path()
        if client_name is None:
            client_name = _random_client_name()
        if kicad_token is None:
            kicad_token = _default_kicad_token()
        self._client = KiCadClient(socket_path, client_name, kicad_token, timeout_ms)

    @staticmethod
    def from_client(client: KiCadClient):
        """Creates a KiCad object from an existing KiCad client"""
        k = KiCad.__new__(KiCad)
        k._client = client
        return k

    def get_version(self) -> KiCadVersion:
        """Returns the KiCad version as a string, including any package-specific info"""
        response = self._client.send(commands.GetVersion(), commands.GetVersionResponse)
        return KiCadVersion.from_proto(response.version)

    def get_api_version(self) -> KiCadVersion:
        """Returns the version of KiCad that this library was built against"""
        return KiCadVersion.from_git_describe(KICAD_API_VERSION)

    def check_version(self) -> bool:
        """Checks if the connected KiCad version matches the version this library was built against"""
        kicad_version = self.get_version()
        api_version = self.get_api_version()

        if kicad_version > api_version:
            raise FutureVersionError(
                f"Warning: Connected KiCad version ({kicad_version}) is newer than "
                f"the API version of kicad-python ({api_version})"
            )

        return True

    def ping(self):
        self._client.send(commands.Ping(), Empty)

    def get_kicad_binary_path(self, binary_name: str) -> str:
        """Returns the full path to the given KiCad binary

        :param binary_name: The short name of the binary, such as `kicad-cli` or `kicad-cli.exe`.
                            If on Windows, an `.exe` extension will be assumed if not present.
        :return: The full path to the binary
        """
        cmd = commands.GetKiCadBinaryPath()
        cmd.binary_name = binary_name
        return self._client.send(cmd, commands.PathResponse).path

    def get_plugin_settings_path(self, identifier: str) -> str:
        """Return a writeable path that a plugin can use for storing persistent data such as
        configuration files, etc.  This path may not yet exist; actual creation of the directory
        for a given plugin is up to the plugin itself.  Files in this path will not be modified if
        the plugin is uninstalled or upgraded.

        :param identifier: should be the full identifier of the plugin (e.g. org.kicad.myplugin)
        :return: a path, with local separators, that the plugin can use for storing settings
        """
        cmd = commands.GetPluginSettingsPath()
        cmd.identifier = identifier
        return self._client.send(cmd, commands.StringResponse).response

    def run_action(self, action: str):
        """Runs a KiCad tool action, if it is available

        WARNING: This is an unstable API and is not intended for use other
        than by API developers. KiCad does not guarantee the stability of
        action names, and running actions may have unintended side effects.
        :param action: the name of a KiCad TOOL_ACTION
        :return: a value from the KIAPI.COMMON.COMMANDS.RUN_ACTION_STATUS enum
        """
        command = commands.RunAction()
        command.action = action
        return self._client.send(command, commands.RunActionResponse)

    def get_open_documents(self, doc_type: DocumentType.ValueType) -> Sequence[DocumentSpecifier]:
        """Retrieves a list of open documents matching the given type"""
        command = commands.GetOpenDocuments()
        command.type = doc_type
        response = self._client.send(command, commands.GetOpenDocumentsResponse)
        return response.documents

    def get_project(self, document: DocumentSpecifier) -> Project:
        """Returns a Project object for the given document"""
        return Project(self._client, document)

    def get_board(self) -> Board:
        """Retrieves a reference to the PCB open in KiCad, if one exists"""
        docs = self.get_open_documents(DocumentType.DOCTYPE_PCB)
        if len(docs) == 0:
            raise ApiError("Expected to be able to retrieve at least one board")
        return Board(self._client, docs[0])

    # Utility functions

    def get_text_extents(self, text: Text) -> Box2:
        """Returns the bounding box of the given text object"""
        cmd = base_commands_pb2.GetTextExtents()
        cmd.text.CopyFrom(text.proto)
        reply = self._client.send(cmd, base_types_pb2.Box2)
        return Box2.from_proto(reply)

    def get_text_as_shapes(
        self, texts: Union[Text, TextBox, Sequence[Union[Text, TextBox]]]
    ) -> list[CompoundShape]:
        """Returns polygonal shapes representing the given text objects"""
        if isinstance(texts, Text) or isinstance(texts, TextBox):
            texts = [texts]

        cmd = base_commands_pb2.GetTextAsShapes()
        for t in texts:
            inner = base_commands_pb2.TextOrTextBox()
            if isinstance(t, Text):
                inner.text.CopyFrom(t.proto)
            else:
                inner.textbox.CopyFrom(t.proto)
            cmd.text.append(inner)

        reply = self._client.send(cmd, base_commands_pb2.GetTextAsShapesResponse)

        return [CompoundShape(entry.shapes) for entry in reply.text_with_shapes]
