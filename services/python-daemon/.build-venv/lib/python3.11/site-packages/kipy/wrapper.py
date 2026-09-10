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

from abc import ABC, abstractmethod
from typing import Optional

import sys

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from google.protobuf.message import Message
from kipy.proto.common.types.base_types_pb2 import KIID


class Wrapper(ABC):
    def __init__(
        self, proto: Optional[Message] = None, proto_ref: Optional[Message] = None
    ):
        pass

    @property
    def proto(self):
        self._pack()
        return self.__dict__["_proto"]

    def _pack(self):
        """Used in some cases to ensure the internal proto state matches the Python
        class instance, for subclasses where the properties are not directly acting on
        the proto object.
        """
        pass


class Item(Wrapper):
    @property
    @abstractmethod
    def id(self) -> KIID:
        return KIID()

    def clone(self) -> Self:
        """Creates a copy of this item with the ID field cleared, so that it can be passed to
        create_items where KiCad will generate a new unique ID for it

        .. versionadded:: 0.8.0"""
        new_proto = self.proto.__class__()
        new_proto.CopyFrom(self.proto)
        new_proto.ClearField("id")
        return self.__class__(proto=new_proto)
