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

from time import sleep
from typing import List, Dict, Union, Iterable, Optional, Sequence, cast, overload
from google.protobuf.empty_pb2 import Empty

from kipy.board_types import (
    ArcTrack,
    Barcode,
    BoardEditorAppearanceSettings,
    BoardItem,
    ReferenceImage,
    BoardText,
    BoardTextBox,
    Dimension,
    FootprintInstance,
    Net,
    Pad,
    BoardShape,
    Track,
    Via,
    Zone,
    Group,
    to_concrete_board_shape,
    to_concrete_dimension,
    unwrap
)
from kipy.client import ApiError, KiCadClient
from kipy.common_types import Color, Commit, TitleBlockInfo, TextAttributes
from kipy.geometry import Box2, PolygonWithHoles, Vector2
from kipy.project import Project, NetClass
from kipy.proto.board import board_types_pb2
from kipy.proto.common.commands import editor_commands_pb2, project_commands_pb2
from kipy.proto.common.envelope_pb2 import ApiStatusCode
from kipy.util import pack_any
from kipy.wrapper import Item, Wrapper

from kipy.proto.common.commands import Ping
from kipy.proto.common.types import DocumentSpecifier, KIID, KiCadObjectType, base_types_pb2
from kipy.proto.common.commands.editor_commands_pb2 import (
    BeginCommit, BeginCommitResponse, CommitAction,
    EndCommit, EndCommitResponse,
    CreateItems, CreateItemsResponse,
    UpdateItems, UpdateItemsResponse,
    GetItems, GetItemsById, GetItemsResponse,
    DeleteItems, DeleteItemsResponse,
    HitTest, HitTestResponse, HitTestResult
)
from kipy.proto.board import board_pb2
from kipy.proto.board import board_commands_pb2

# Re-exported protobuf enum types
from kipy.proto.board.board_pb2 import (    # noqa
    BoardLayerClass,
    BoardEdgeConnectorType,
    DielectricModel,
    BoardStackupDielectricType,
)
from kipy.proto.board.board_types_pb2 import ( #noqa
    BoardLayer
)
from kipy.proto.board.board_commands_pb2 import ( #noqa
    BoardOriginType,
    BoardFlipDirection
)

class BoardLayerGraphicsDefaults(Wrapper):
    """The default properties for graphic items added on a given class of board layer"""
    def __init__(self, proto: Optional[board_pb2.BoardLayerGraphicsDefaults] = None):
        self._proto = board_pb2.BoardLayerGraphicsDefaults()

        if proto is not None:
            self._proto.CopyFrom(proto)
    @property
    def layer(self) -> board_pb2.BoardLayerClass.ValueType:
        """The layer class that these defaults apply to"""
        return self._proto.layer

    @layer.setter
    def layer(self, value: board_pb2.BoardLayerClass.ValueType):
        self._proto.layer = value

    @property
    def line_thickness(self) -> int:
        return self._proto.line_thickness.value_nm

    @line_thickness.setter
    def line_thickness(self, value: int):
        self._proto.line_thickness.value_nm = value

    @property
    def text(self) -> TextAttributes:
        return TextAttributes(self._proto.text)

class BoardStackupDielectricProperties(Wrapper):
    def __init__(self, proto: Optional[board_pb2.BoardStackupDielectricProperties] = None):
        self._proto = board_pb2.BoardStackupDielectricProperties()
        if proto:
            self._proto.CopyFrom(proto)

    @property
    def epsilon_r(self) -> float:
        return self._proto.epsilon_r

    @epsilon_r.setter
    def epsilon_r(self, epsilon_r: float):
        self._proto.epsilon_r = epsilon_r

    @property
    def loss_tangent(self) -> float:
        return self._proto.loss_tangent

    @loss_tangent.setter
    def loss_tangent(self, loss_tangent: float):
        self._proto.loss_tangent = loss_tangent

    @property
    def material_name(self) -> str:
        return self._proto.material_name

    @material_name.setter
    def material_name(self, name: str):
        self._proto.material_name = name

    @property
    def thickness(self) -> int:
        return self._proto.thickness.value_nm

    @thickness.setter
    def thickness(self, thickness: int):
        self._proto.thickness.value_nm = thickness

    @property
    def thickness_locked(self) -> bool:
        """Whether the layer thickness is locked (for impedance controlled layers)

        .. versionadded:: 0.8.0 (KiCad 10.0.6)
        """
        return self._proto.thickness_locked

    @thickness_locked.setter
    def thickness_locked(self, locked: bool):
        self._proto.thickness_locked = locked

    @property
    def spec_frequency(self) -> Optional[float]:
        """The frequency at which the dielectric properties were measured, in Hz

        .. versionadded:: 0.8.0 (KiCad 11.0)
        """
        if self._proto.HasField("spec_frequency"):
            return self._proto.spec_frequency
        return None

    @spec_frequency.setter
    def spec_frequency(self, frequency: Optional[float]):
        if frequency is None:
            self._proto.ClearField("spec_frequency")
        else:
            self._proto.spec_frequency = frequency

    @property
    def dielectric_model(self) -> board_pb2.DielectricModel.ValueType:
        """The model used to extrapolate dielectric properties across frequency

        .. versionadded:: 0.8.0 (KiCad 11.0)
        """
        return self._proto.dielectric_model

    @dielectric_model.setter
    def dielectric_model(self, model: board_pb2.DielectricModel.ValueType):
        self._proto.dielectric_model = model


class BoardStackupDielectricLayer(Wrapper):
    def __init__(self, proto: Optional[board_pb2.BoardStackupDielectricLayer] = None):
        self._proto = board_pb2.BoardStackupDielectricLayer()
        if proto:
            self._proto.CopyFrom(proto)

    @property
    def layers(self) -> List[BoardStackupDielectricProperties]:
        """Each dielectric layer may be made up of one or more sub-layers with different properties"""
        return [BoardStackupDielectricProperties(layer) for layer in self._proto.layer]

    @property
    def type(self) -> board_pb2.BoardStackupDielectricType.ValueType:
        """The physical type of this dielectric slot (e.g. core or prepreg)

        .. versionadded:: 0.8.0 (KiCad 10.0.6)
        """
        return self._proto.type

    @type.setter
    def type(self, value: board_pb2.BoardStackupDielectricType.ValueType):
        self._proto.type = value


class BoardStackupSoldermaskLayer(Wrapper):
    """Properties of a soldermask layer

    .. versionadded:: 0.8.0 (KiCad 10.0.6)"""

    def __init__(self, proto: Optional[board_pb2.BoardStackupSoldermaskLayer] = None):
        self._proto = board_pb2.BoardStackupSoldermaskLayer()
        if proto:
            self._proto.CopyFrom(proto)

    @property
    def epsilon_r(self) -> float:
        return self._proto.epsilon_r

    @epsilon_r.setter
    def epsilon_r(self, value: float):
        self._proto.epsilon_r = value

    @property
    def loss_tangent(self) -> float:
        return self._proto.loss_tangent

    @loss_tangent.setter
    def loss_tangent(self, value: float):
        self._proto.loss_tangent = value

    @property
    def material_name(self) -> str:
        return self._proto.material_name

    @material_name.setter
    def material_name(self, value: str):
        self._proto.material_name = value

    @property
    def thickness(self) -> int:
        return self._proto.thickness.value_nm

    @thickness.setter
    def thickness(self, value: int):
        self._proto.thickness.value_nm = value


class BoardStackupSilkscreenLayer(Wrapper):
    """Properties of a silkscreen layer

    .. versionadded:: 0.8.0 (KiCad 10.0.6)"""

    def __init__(self, proto: Optional[board_pb2.BoardStackupSilkscreenLayer] = None):
        self._proto = board_pb2.BoardStackupSilkscreenLayer()
        if proto:
            self._proto.CopyFrom(proto)

    @property
    def material_name(self) -> str:
        return self._proto.material_name

    @material_name.setter
    def material_name(self, value: str):
        self._proto.material_name = value


class BoardStackupLayer(Wrapper):
    def __init__(self, proto: Optional[board_pb2.BoardStackupLayer] = None):
        self._proto = board_pb2.BoardStackupLayer()
        if proto:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:
        return (
            f"BoardStackupLayer(layer={BoardLayer.Name(self.layer)}, user_name={self.user_name},"
            f"thickness={self.thickness}, enabled={self.enabled}, type={self.type},"
            f"material_name={self.material_name})"
        )

    @property
    def thickness(self) -> int:
        """The total thickness of this layer, in nanometers.  If this is a dielectric layer, this
        thickness may be the sum of multiple sub-layers."""
        return self._proto.thickness.value_nm

    @thickness.setter
    def thickness(self, value: int):
        self._proto.thickness.value_nm = value

    @property
    def layer(self) -> BoardLayer.ValueType:
        """The board layer this stackup entry corresponds to, or BL_UNDEFINED if this entry is
        a dielectric layer"""
        return self._proto.layer

    @layer.setter
    def layer(self, value: BoardLayer.ValueType):
        self._proto.layer = value

    @property
    def enabled(self) -> bool:
        return self._proto.enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._proto.enabled = value

    @property
    def type(self) -> board_pb2.BoardStackupLayerType.ValueType:
        return self._proto.type

    @type.setter
    def type(self, value: board_pb2.BoardStackupLayerType.ValueType):
        self._proto.type = value

    @property
    def dielectric(self) -> Optional[BoardStackupDielectricLayer]:
        """Dielectric details, if this layer is a dielectric layer

        .. versionadded:: 0.8.0 (KiCad 10.0.6)
        """
        if self._proto.WhichOneof("details") == "dielectric":
            return BoardStackupDielectricLayer(self._proto.dielectric)
        return None

    @dielectric.setter
    def dielectric(self, value: BoardStackupDielectricLayer):
        self._proto.dielectric.CopyFrom(value.proto)

    @property
    def soldermask(self) -> Optional[BoardStackupSoldermaskLayer]:
        """Soldermask details, if this layer is a soldermask layer

        .. versionadded:: 0.8.0 (KiCad 10.0.6)
        """
        if self._proto.WhichOneof("details") == "soldermask":
            return BoardStackupSoldermaskLayer(self._proto.soldermask)
        return None

    @soldermask.setter
    def soldermask(self, value: BoardStackupSoldermaskLayer):
        self._proto.soldermask.CopyFrom(value.proto)

    @property
    def silkscreen(self) -> Optional[BoardStackupSilkscreenLayer]:
        """Silkscreen details, if this layer is a silkscreen layer

        .. versionadded:: 0.8.0 (KiCad 10.0.6)
        """
        if self._proto.WhichOneof("details") == "silkscreen":
            return BoardStackupSilkscreenLayer(self._proto.silkscreen)
        return None

    @silkscreen.setter
    def silkscreen(self, value: BoardStackupSilkscreenLayer):
        self._proto.silkscreen.CopyFrom(value.proto)

    @property
    def color(self) -> Color:
        return Color(self._proto.color)

    @color.setter
    def color(self, value: Color):
        self._proto.color.CopyFrom(value.proto)

    @property
    def material_name(self) -> str:
        return self._proto.material_name

    @material_name.setter
    def material_name(self, value: str):
        self._proto.material_name = value

    @property
    def user_name(self) -> str:
        """The name of the layer shown in the KiCad GUI, which may be a default value like "F.Cu"
        or may have been customized by the user. This field does not apply to dielectric layers."""
        return self._proto.user_name

    @user_name.setter
    def user_name(self, value: str):
        self._proto.user_name = value


class BoardFinish(Wrapper):
    """The board finish (e.g. ENIG, HASL, OSP) applied to exposed copper

    .. versionadded:: 0.8.0 (KiCad 10.0.6)"""

    def __init__(self, proto: Optional[board_pb2.BoardFinish] = None):
        self._proto = board_pb2.BoardFinish()
        if proto:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:
        return f"BoardFinish(type_name={self.type_name!r})"

    @property
    def type_name(self) -> str:
        """The finish type name"""
        return self._proto.type_name

    @type_name.setter
    def type_name(self, value: str):
        self._proto.type_name = value


class BoardImpedanceControl(Wrapper):
    """Whether impedance-controlled routing is enabled for this board

    .. versionadded:: 0.8.0 (KiCad 10.0.6)"""

    def __init__(self, proto: Optional[board_pb2.BoardImpedanceControl] = None):
        self._proto = board_pb2.BoardImpedanceControl()
        if proto:
            self._proto.CopyFrom(proto)

    @property
    def is_controlled(self) -> bool:
        """True if the board uses impedance-controlled widths"""
        return self._proto.is_controlled

    @is_controlled.setter
    def is_controlled(self, value: bool):
        self._proto.is_controlled = value


class BoardEdgeConnector(Wrapper):
    """The type of edge connector present on the board

    .. versionadded:: 0.8.0 (KiCad 10.0.6)"""

    def __init__(self, proto: Optional[board_pb2.BoardEdgeConnector] = None):
        self._proto = board_pb2.BoardEdgeConnector()
        if proto:
            self._proto.CopyFrom(proto)

    @property
    def type(self) -> board_pb2.BoardEdgeConnectorType.ValueType:
        return self._proto.type

    @type.setter
    def type(self, value: board_pb2.BoardEdgeConnectorType.ValueType):
        self._proto.type = value


class EdgePlating(Wrapper):
    """Whether the board edges are plated

    .. versionadded:: 0.8.0 (KiCad 10.0.6)"""

    def __init__(self, proto: Optional[board_pb2.EdgePlating] = None):
        self._proto = board_pb2.EdgePlating()
        if proto:
            self._proto.CopyFrom(proto)

    @property
    def has_edge_plating(self) -> bool:
        """True if board edges are plated with copper"""
        return self._proto.has_edge_plating

    @has_edge_plating.setter
    def has_edge_plating(self, value: bool):
        self._proto.has_edge_plating = value


class BoardEdgeSettings(Wrapper):
    """Settings related to board edges, such as connectors and plating

    .. versionadded:: 0.8.0 (KiCad 10.0.6)"""

    def __init__(self, proto: Optional[board_pb2.BoardEdgeSettings] = None):
        self._proto = board_pb2.BoardEdgeSettings()
        if proto:
            self._proto.CopyFrom(proto)

    @property
    def connector(self) -> BoardEdgeConnector:
        return BoardEdgeConnector(self._proto.connector)

    @connector.setter
    def connector(self, value: BoardEdgeConnector):
        self._proto.connector.CopyFrom(value.proto)

    @property
    def plating(self) -> EdgePlating:
        return EdgePlating(self._proto.plating)

    @plating.setter
    def plating(self, value: EdgePlating):
        self._proto.plating.CopyFrom(value.proto)


class BoardStackup(Wrapper):
    def __init__(self, proto: Optional[board_pb2.BoardStackup] = None):
        self._proto = board_pb2.BoardStackup()
        if proto:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:
        return f"BoardStackup(layers={self.layers})"

    @property
    def finish(self) -> BoardFinish:
        """The board finish (e.g. ENIG, HASL, OSP)

        .. versionadded:: 0.8.0
        """
        return BoardFinish(self._proto.finish)

    @finish.setter
    def finish(self, value: BoardFinish):
        self._proto.finish.CopyFrom(value.proto)

    @property
    def impedance(self) -> BoardImpedanceControl:
        """Whether impedance-controlled routing is enabled

        .. versionadded:: 0.8.0
        """
        return BoardImpedanceControl(self._proto.impedance)

    @impedance.setter
    def impedance(self, value: BoardImpedanceControl):
        self._proto.impedance.CopyFrom(value.proto)

    @property
    def edge(self) -> BoardEdgeSettings:
        """Edge connector and plating settings

        .. versionadded:: 0.8.0
        """
        return BoardEdgeSettings(self._proto.edge)

    @edge.setter
    def edge(self, value: BoardEdgeSettings):
        self._proto.edge.CopyFrom(value.proto)

    @property
    def layers(self) -> List[BoardStackupLayer]:
        """The stackup layers, in order from top to bottom of the board"""
        return [BoardStackupLayer(layer) for layer in self._proto.layers]

class Board:
    def __init__(self, kicad: KiCadClient, document: DocumentSpecifier):
        """Represents an open board (.kicad_pcb) document in KiCad"""
        self._kicad = kicad
        self._doc = document

    def __repr__(self) -> str:
        return f"Board(filename={self.name})"

    @property
    def client(self) -> KiCadClient:
        """The KiCad client used to communicate with the API server"""
        return self._kicad

    @property
    def document(self) -> DocumentSpecifier:
        """The document specifier for the board"""
        return self._doc

    def get_project(self) -> Project:
        """Returns the project that this board is a part of"""
        return Project(self._kicad, self._doc)

    @property
    def name(self) -> str:
        """Returns the file name of the board"""
        return self._doc.board_filename

    def save(self):
        command = editor_commands_pb2.SaveDocument()
        command.document.CopyFrom(self._doc)
        self._kicad.send(command, Empty)

    def save_as(self, filename: str, overwrite: bool = False, include_project: bool = True):
        """Saves the board to a new file.

        :param filename: The path to save the board to
        :param overwrite: If True, the file will be overwritten if it already exists
        :param include_project: If True, the project will be saved along with the board
        """
        command = editor_commands_pb2.SaveCopyOfDocument()
        command.document.CopyFrom(self._doc)
        command.path = filename
        command.options.overwrite = overwrite
        command.options.include_project = include_project
        self._kicad.send(command, Empty)

    def revert(self):
        """Reverts the board to the last saved state"""
        command = editor_commands_pb2.RevertDocument()
        command.document.CopyFrom(self._doc)
        self._kicad.send(command, Empty)

    def begin_commit(self) -> Commit:
        """Begins a commit transaction on the board, returning a Commit object that can be used to
        push or drop (cancel) the commit.  Each commit represents a set of changes that can be
        undone or redone as a single operation.

        If you do not call begin_commit, any changes made to the board will be committed
        immediately, which will result in multiple steps being added to the undo history.

        If you call begin_commit, changes made to the board will not be reflected in the editor
        until you call push_commit.  This allows you to group multiple changes into a single undo
        step.
        """
        command = BeginCommit()
        return Commit(self._kicad.send(command, BeginCommitResponse).id)

    def push_commit(self, commit: Commit, message: str = ""):
        """If a commit is open, pushes the changes to the board and closes the commit.  This will
        result in a single undo step being added to the undo history."""
        command = EndCommit()
        command.id.CopyFrom(commit.id)
        command.action = CommitAction.CMA_COMMIT
        command.message = message
        self._kicad.send(command, EndCommitResponse)

    def drop_commit(self, commit: Commit):
        """Cancel a commit, discarding any changes made since the commit was opened"""
        command = EndCommit()
        command.id.CopyFrom(commit.id)
        command.action = CommitAction.CMA_DROP
        self._kicad.send(command, EndCommitResponse)

    def create_items(self, items: Union[Wrapper, Iterable[Wrapper]]) -> List[Wrapper]:
        command = CreateItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, Wrapper):
            command.items.append(pack_any(items.proto))
        else:
            command.items.extend([pack_any(i.proto) for i in items])

        return [
            unwrap(result.item)
            for result in self._kicad.send(command, CreateItemsResponse).created_items
        ]

    def _to_concrete_items(self, items: Sequence[Wrapper]) -> List[BoardItem]:
        items_converted: List[BoardItem] = []
        for it in items:
            assert isinstance(it, BoardItem)

            if isinstance(it, BoardShape):
                items_converted.append(to_concrete_board_shape(cast(BoardShape, it)))
            elif isinstance(it, Dimension):
                items_converted.append(to_concrete_dimension(cast(Dimension, it)))
            else:
                items_converted.append(it)
        return items_converted

    def get_items(
        self, types: Union[KiCadObjectType.ValueType, Sequence[KiCadObjectType.ValueType]]
    ) -> Sequence[Item]:
        """Retrieves items from the board, optionally filtering to a single or set of types"""
        command = GetItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(types, int):
            command.types.append(types)
        else:
            command.types.extend(types)

        return self._to_concrete_items(
            [unwrap(item) for item in self._kicad.send(command, GetItemsResponse).items]
        )

    def get_items_by_id(
        self, ids: Union[KIID, Sequence[KIID]]
    ) -> Sequence[Item]:
        """Retrieves items from the board by their KIID (internal unique identifier)

        .. versionadded:: 0.7.0 (KiCad 10.0.0)
        """
        command = GetItemsById()
        command.header.document.CopyFrom(self._doc)
        if isinstance(ids, KIID):
            command.items.append(ids)
        else:
            command.items.extend(ids)

        return self._to_concrete_items(
            [unwrap(item) for item in self._kicad.send(command, GetItemsResponse).items]
        )

    def get_items_by_net(
        self,
        nets: Union[Net, Sequence[Net]],
        types: Optional[
            Union[KiCadObjectType.ValueType, Sequence[KiCadObjectType.ValueType]]
        ] = None,
    ) -> Sequence[Item]:
        """Retrieves items from the board, filtered by one or more nets

        .. versionadded:: 0.7.0 (KiCad 10.0.1)"""
        command = board_commands_pb2.GetItemsByNet()
        command.header.document.CopyFrom(self._doc)

        if isinstance(types, int):
            command.types.append(types)
        elif types is not None:
            command.types.extend(types)

        if isinstance(nets, Net):
            command.nets.append(nets.proto)
        else:
            command.nets.extend([net.proto for net in nets])

        return self._to_concrete_items(
            [unwrap(item) for item in self._kicad.send(command, GetItemsResponse).items]
        )

    def get_items_by_netclass(
        self,
        net_classes: Union[str, Sequence[str]],
        types: Optional[
            Union[KiCadObjectType.ValueType, Sequence[KiCadObjectType.ValueType]]
        ] = None,
    ) -> Sequence[Item]:
        """Retrieves items from the board, filtered by one or more net class names

        .. versionadded:: 0.7.0 (KiCad 10.0.1)"""
        command = board_commands_pb2.GetItemsByNetClass()
        command.header.document.CopyFrom(self._doc)

        if isinstance(types, int):
            command.types.append(types)
        elif types is not None:
            command.types.extend(types)

        if isinstance(net_classes, str):
            command.net_classes.append(net_classes)
        else:
            command.net_classes.extend(net_classes)

        return self._to_concrete_items(
            [unwrap(item) for item in self._kicad.send(command, GetItemsResponse).items]
        )

    def get_connected_items(
        self,
        items: Union[BoardItem, KIID, Sequence[Union[BoardItem, KIID]]],
        types: Optional[
            Union[KiCadObjectType.ValueType, Sequence[KiCadObjectType.ValueType]]
        ] = None,
    ) -> Sequence[Item]:
        """Retrieves items that are copper-connected to the given source item(s) or item IDs

        .. versionadded:: 0.7.0 (KiCad 10.0.1)"""
        command = board_commands_pb2.GetConnectedItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(types, int):
            command.types.append(types)
        elif types is not None:
            command.types.extend(types)

        source_items = [items] if isinstance(items, (BoardItem, KIID)) else items

        for source in source_items:
            command.items.append(source.id if isinstance(source, BoardItem) else source)

        return self._to_concrete_items(
            [unwrap(item) for item in self._kicad.send(command, GetItemsResponse).items]
        )

    def get_tracks(self) -> Sequence[Union[Track, ArcTrack]]:
        """Retrieves all tracks and arc tracks on the board"""
        return [
            cast(Track, item) if isinstance(item, Track) else cast(ArcTrack, item)
            for item in self.get_items(
                types=[KiCadObjectType.KOT_PCB_TRACE, KiCadObjectType.KOT_PCB_ARC]
            )
        ]

    def get_vias(self) -> Sequence[Via]:
        """Retrieves all vias on the board"""
        return [cast(Via, item) for item in self.get_items(types=[KiCadObjectType.KOT_PCB_VIA])]

    def get_pads(self) -> Sequence[Pad]:
        """Retrieves all pads on the board (note that pads belong to footprints, not the board
        itself)"""
        return [cast(Pad, item) for item in self.get_items(types=[KiCadObjectType.KOT_PCB_PAD])]

    def get_footprints(self) -> Sequence[FootprintInstance]:
        """Retrieves all footprints on the board"""
        return [
            cast(FootprintInstance, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_PCB_FOOTPRINT])
        ]

    def get_shapes(self) -> Sequence[BoardShape]:
        """Retrieves all graphic shapes (not including tracks or text) on the board"""
        return [
            item
            for item in (
                to_concrete_board_shape(cast(BoardShape, item))
                for item in self.get_items(types=[KiCadObjectType.KOT_PCB_SHAPE])
            )
            if item is not None
        ]

    def get_dimensions(self) -> Sequence[Dimension]:
        """Retrieves all dimension objects on the board"""
        return [
            item
            for item in (
                to_concrete_dimension(cast(Dimension, item))
                for item in self.get_items(types=[KiCadObjectType.KOT_PCB_DIMENSION])
            )
            if item is not None
        ]

    def get_text(self) -> Sequence[Union[BoardText, BoardTextBox]]:
        """Retrieves all text objects on the board"""
        return [
            cast(BoardText, item) if isinstance(item, BoardText) else cast(BoardTextBox, item)
            for item in self.get_items(
                types=[KiCadObjectType.KOT_PCB_TEXT, KiCadObjectType.KOT_PCB_TEXTBOX]
            )
        ]

    def get_barcodes(self) -> Sequence[Barcode]:
        """Retrieves all barcode objects on the board

        .. versionadded:: 0.7.0"""
        return [
            cast(Barcode, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_PCB_BARCODE])
        ]

    def get_reference_images(self) -> Sequence[ReferenceImage]:
        """Retrieves all reference image objects on the board

        .. versionadded:: 0.7.0"""
        return [
            cast(ReferenceImage, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_PCB_REFERENCE_IMAGE])
        ]

    def get_zones(self) -> Sequence[Zone]:
        """Retrieves all zones (including rule areas and graphic zones) on the board"""
        return [cast(Zone, item) for item in self.get_items(types=[KiCadObjectType.KOT_PCB_ZONE])]

    def get_groups(self) -> Sequence[Group]:
        """Retrieves all groups on the board

        .. versionadded:: 0.7.0 (KiCad 10.0.0)"""
        groups = [cast(Group, item) for item in self.get_items(types=[KiCadObjectType.KOT_PCB_GROUP])]

        # Unwrap items in groups
        if len(groups) > 0:
            for group in groups:
                items = self.get_items_by_id(group._item_ids)
                group._unwrapped_items = items

        return groups

    def get_as_string(self) -> str:
        """Returns the board as a string in KiCad's board file format"""
        command = editor_commands_pb2.SaveDocumentToString()
        command.document.CopyFrom(self._doc)
        return self._kicad.send(command, editor_commands_pb2.SavedDocumentResponse).contents

    def get_selection_as_string(self) -> str:
        """Returns the current selection as a string in KiCad's board file format"""
        command = editor_commands_pb2.SaveSelectionToString()
        return self._kicad.send(command, editor_commands_pb2.SavedSelectionResponse).contents

    def update_items(self, items: Union[BoardItem, Sequence[BoardItem]]) -> List[BoardItem]:
        """Updates the properties of one or more items on the board.  The items must already exist
        on the board, and are matched by internal UUID.  All other properties of the items are
        updated from those passed in this call.

        Returns the updated items, which may be different from the input items if any updates
        failed to apply (for example, if any properties were out of range and were clamped)"""
        command = UpdateItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, BoardItem):
            command.items.append(pack_any(items.proto))
        else:
            command.items.extend([pack_any(i.proto) for i in items])

        if len(command.items) == 0:
            return []

        return self._to_concrete_items(
            [
                unwrap(result.item)
                for result in self._kicad.send(
                    command, UpdateItemsResponse
                ).updated_items
            ]
        )

    def remove_items(self, items: Union[BoardItem, Sequence[BoardItem]]):
        """Deletes one or more items from the board"""
        command = DeleteItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, BoardItem):
            command.item_ids.append(items.id)
        else:
            command.item_ids.extend([item.id for item in items])

        if len(command.item_ids) == 0:
            return

        self._kicad.send(command, DeleteItemsResponse)

    def remove_items_by_id(self, items: Union[KIID, Sequence[KIID]]):
        """Deletes one or more items from the board using their unique IDs

        .. versionadded:: 0.4.0"""
        command = DeleteItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, KIID):
            command.item_ids.append(items)
        else:
            command.item_ids.extend(items)

        if len(command.item_ids) == 0:
            return

        self._kicad.send(command, DeleteItemsResponse)

    def flip_items(
        self,
        items: Union[BoardItem, Sequence[BoardItem]],
        direction: board_commands_pb2.BoardFlipDirection.ValueType = BoardFlipDirection.BFD_LEFT_RIGHT,
    ) -> List[BoardItem]:
        """Flips one or more board items to the opposite side of the board.

        The given items must already exist on the board; each is flipped in place and the
        Python item passed in is updated with the new state from KiCad.  Returns the set
        of items that were successfully flipped.

        :param items: one or more board items to flip
        :param direction: ``BFD_LEFT_RIGHT`` (mirror around the Y axis) or
                          ``BFD_TOP_BOTTOM`` (mirror around the X axis)

        .. versionadded:: 0.8.0 (KiCad 10.0.6)"""
        command = board_commands_pb2.FlipItems()
        command.header.document.CopyFrom(self._doc)
        command.direction = direction

        if isinstance(items, BoardItem):
            items = [items]
        else:
            items = list(items)

        command.items.extend([item.id for item in items])

        if len(command.items) == 0:
            return []

        response = self._kicad.send(command, board_commands_pb2.FlipItemsResponse)

        flipped: List[BoardItem] = []
        for item, result in zip(items, response.flipped_items):
            if result.status.code != editor_commands_pb2.ItemStatusCode.ISC_OK:
                continue
            updated = self._to_concrete_items([unwrap(result.item)])[0]
            item.proto.CopyFrom(updated.proto)
            flipped.append(updated)
        return flipped

    def flip_items_by_id(
        self,
        items: Union[KIID, Sequence[KIID]],
        direction: board_commands_pb2.BoardFlipDirection.ValueType = BoardFlipDirection.BFD_LEFT_RIGHT,
    ) -> List[BoardItem]:
        """Flips one or more board items to the opposite side of the board by their unique IDs.

        Returns the flipped items as returned by KiCad.  Items that could not be flipped (for
        example because the ID doesn't exist or the type is not a flippable board item) will be
        omitted.

        :param items: one or more item IDs (KIID) to flip
        :param direction: ``BFD_LEFT_RIGHT`` (mirror around the Y axis) or
                          ``BFD_TOP_BOTTOM`` (mirror around the X axis)

        .. versionadded:: 0.8.0 (KiCad 10.0.6)"""
        command = board_commands_pb2.FlipItems()
        command.header.document.CopyFrom(self._doc)
        command.direction = direction

        if isinstance(items, KIID):
            command.items.append(items)
        else:
            command.items.extend(items)

        if len(command.items) == 0:
            return []

        response = self._kicad.send(command, board_commands_pb2.FlipItemsResponse)

        return self._to_concrete_items(
            [
                unwrap(result.item)
                for result in response.flipped_items
                if result.status.code == editor_commands_pb2.ItemStatusCode.ISC_OK
            ]
        )

    def get_nets(
        self, netclass_filter: Optional[Union[str, Sequence[str]]] = None
    ) -> Sequence[Net]:
        """Retrieves all nets on the board, optionally filtering by net class"""
        command = board_commands_pb2.GetNets()
        command.board.CopyFrom(self._doc)

        if isinstance(netclass_filter, str):
            command.netclass_filter.append(netclass_filter)
        elif netclass_filter is not None:
            command.netclass_filter.extend(netclass_filter)

        return [
            Net(net)
            for net in self._kicad.send(command, board_commands_pb2.NetsResponse).nets
        ]

    def get_netclass_for_nets(self, nets: Union[Net, Sequence[Net]]) -> Dict[str, NetClass]:
        """Retrieves the net class for one or more nets on the board"""
        cmd = board_commands_pb2.GetNetClassForNets()
        if isinstance(nets, Net):
            cmd.net.append(nets.proto)
        else:
            cmd.net.extend([net.proto for net in nets])

        response = self._kicad.send(cmd, board_commands_pb2.NetClassForNetsResponse)
        return {key: NetClass(value) for key, value in response.classes.items()}

    def get_selection(
        self,
        types: Optional[
            Union[KiCadObjectType.ValueType, Sequence[KiCadObjectType.ValueType]]
        ] = None,
    ) -> Sequence[Wrapper]:
        cmd = editor_commands_pb2.GetSelection()
        cmd.header.document.CopyFrom(self._doc)

        if isinstance(types, int):
            cmd.types.append(types)
        else:
            cmd.types.extend(types or [])

        return self._to_concrete_items([
            unwrap(item)
            for item in self._kicad.send(
                cmd, editor_commands_pb2.SelectionResponse
            ).items
        ])

    def add_to_selection(
        self, items: Union[BoardItem, Sequence[BoardItem]]
    ) -> Sequence[Wrapper]:
        """Adds one or more items to the current selection on the board

        :param items: The items to add to the selection
        :return: The updated selection
        """
        cmd = editor_commands_pb2.AddToSelection()
        cmd.header.document.CopyFrom(self._doc)

        if isinstance(items, BoardItem):
            cmd.items.append(items.id)
        else:
            cmd.items.extend([i.id for i in items])

        return [
            unwrap(item)
            for item in self._kicad.send(
                cmd, editor_commands_pb2.SelectionResponse
            ).items
        ]

    def remove_from_selection(
        self, items: Union[BoardItem, Sequence[BoardItem]]
    ) -> Sequence[Wrapper]:
        """Removes one or more items from the current selection on the board

        :param items: The items to remove from the selection
        :return: The updated selection
        """
        cmd = editor_commands_pb2.RemoveFromSelection()
        cmd.header.document.CopyFrom(self._doc)

        if isinstance(items, BoardItem):
            cmd.items.append(items.id)
        else:
            cmd.items.extend([i.id for i in items])

        return [
            unwrap(item)
            for item in self._kicad.send(
                cmd, editor_commands_pb2.SelectionResponse
            ).items
        ]

    def clear_selection(self):
        """Clears the current selection on the board"""
        cmd = editor_commands_pb2.ClearSelection()
        cmd.header.document.CopyFrom(self._doc)
        self._kicad.send(cmd, Empty)

    def get_stackup(self) -> BoardStackup:
        """Retrieves the stackup for the board"""
        command = board_commands_pb2.GetBoardStackup()
        command.board.CopyFrom(self._doc)
        return BoardStackup(
            self._kicad.send(command, board_commands_pb2.BoardStackupResponse).stackup
        )

    def get_copper_layer_count(self) -> int:
        """
        :return: The number of copper layers on the current board

        .. versionadded:: 0.5.0 (with KiCad 9.0.5)
        """
        cmd = board_commands_pb2.GetBoardEnabledLayers()
        cmd.board.CopyFrom(self._doc)
        response = self._kicad.send(cmd, board_commands_pb2.BoardEnabledLayersResponse)
        return response.copper_layer_count

    def get_enabled_layers(self) -> List[board_types_pb2.BoardLayer.ValueType]:
        """
        Retrieves the list of all enabled layers in the board, including copper and non-copper layers.

        :return: A list of enabled BoardLayer enums.

        .. versionadded:: 0.5.0 (with KiCad 9.0.5)
        """
        cmd = board_commands_pb2.GetBoardEnabledLayers()
        cmd.board.CopyFrom(self._doc)
        response = self._kicad.send(cmd, board_commands_pb2.BoardEnabledLayersResponse)
        return list(response.layers)

    def set_enabled_layers(
        self,
        copper_layer_count: int,
        layers: Sequence[board_types_pb2.BoardLayer.ValueType],
    ) -> List[board_types_pb2.BoardLayer.ValueType]:
        """
        Sets the copper layer count and enabled non-copper layers for the board.

        WARNING: Any existing content on layers that are removed by this call is deleted. This operation cannot be undone.

        :param copper_layer_count: The number of copper layers to enable (must be even and >= 2).
        :param layers: The non-copper layers to enable.
        :return: The updated list of enabled BoardLayer enums.

        .. versionadded:: 0.5.0 (with KiCad 9.0.5)
        """
        cmd = board_commands_pb2.SetBoardEnabledLayers()
        cmd.board.CopyFrom(self._doc)
        cmd.copper_layer_count = copper_layer_count
        cmd.layers.extend(layers)
        response = self._kicad.send(cmd, board_commands_pb2.BoardEnabledLayersResponse)
        return list(response.layers)

    def get_graphics_defaults(self) -> Dict[int, BoardLayerGraphicsDefaults]:
        """Retrieves the default graphics properties for each layer class on the board"""
        cmd = board_commands_pb2.GetGraphicsDefaults()
        cmd.board.CopyFrom(self._doc)
        reply = self._kicad.send(cmd, board_commands_pb2.GraphicsDefaultsResponse)
        return {
            board_pb2.BoardLayerClass.BLC_SILKSCREEN:  BoardLayerGraphicsDefaults(reply.defaults.layers[0]),
            board_pb2.BoardLayerClass.BLC_COPPER:      BoardLayerGraphicsDefaults(reply.defaults.layers[1]),
            board_pb2.BoardLayerClass.BLC_EDGES:       BoardLayerGraphicsDefaults(reply.defaults.layers[2]),
            board_pb2.BoardLayerClass.BLC_COURTYARD:   BoardLayerGraphicsDefaults(reply.defaults.layers[3]),
            board_pb2.BoardLayerClass.BLC_FABRICATION: BoardLayerGraphicsDefaults(reply.defaults.layers[4]),
            board_pb2.BoardLayerClass.BLC_OTHER:       BoardLayerGraphicsDefaults(reply.defaults.layers[5])
        }

    def get_title_block_info(self) -> TitleBlockInfo:
        """Retrieves the title block information for the board"""
        cmd = editor_commands_pb2.GetTitleBlockInfo()
        cmd.document.CopyFrom(self._doc)
        return TitleBlockInfo(self._kicad.send(cmd, base_types_pb2.TitleBlockInfo))

    def set_title_block_info(self, title_block: TitleBlockInfo):
        """Sets the title block information for the board

        .. versionadded:: 0.7.0 (with KiCad 10.0.1)"""
        cmd = editor_commands_pb2.SetTitleBlockInfo()
        cmd.document.CopyFrom(self._doc)
        cmd.title_block.CopyFrom(title_block.proto)
        self._kicad.send(cmd, Empty)

    def get_origin(self, origin_type: board_commands_pb2.BoardOriginType.ValueType) -> Vector2:
        """Retrieves the specified (grid or drill/place) board origin

        .. versionadded:: 0.3.0"""
        cmd = board_commands_pb2.GetBoardOrigin()
        cmd.board.CopyFrom(self._doc)
        cmd.type = origin_type
        return Vector2(self._kicad.send(cmd, base_types_pb2.Vector2))

    def set_origin(self, origin_type: board_commands_pb2.BoardOriginType.ValueType,
                   origin: Vector2):
        """Sets the specified (grid or drill/place) board origin

        .. versionadded:: 0.3.0"""
        cmd = board_commands_pb2.SetBoardOrigin()
        cmd.board.CopyFrom(self._doc)
        cmd.type = origin_type
        cmd.origin.CopyFrom(origin.proto)
        self._kicad.send(cmd, Empty)

    def get_layer_name(self, layer: board_types_pb2.BoardLayer.ValueType) -> str:
        """Retrieves the user-visible name of a given layer, which may be a default value like "F.Cu"
        or may have been customized by the user.  This method does not apply to dielectric layers.

        .. versionadded:: 0.6.0 (KiCad 9.0.8)"""
        cmd = board_commands_pb2.GetBoardLayerName()
        cmd.board.CopyFrom(self._doc)
        cmd.layer = layer
        return self._kicad.send(cmd, board_commands_pb2.BoardLayerNameResponse).name

    def get_layer_by_name(self, layer_name: str) -> board_types_pb2.BoardLayer.ValueType:
        """Retrieves a board layer ID from the given name, which may be either a KiCad standard
        layer name (e.g. `In1.Cu`) or a user-defined name in the current board.  Returns
        BL_UNDEFINED if the given name doesn't map to any layer in the current board.

        .. versionadded:: 0.8.0 (KiCad 10.0.6)"""
        cmd = board_commands_pb2.GetBoardLayerByName()
        cmd.board.CopyFrom(self._doc)
        cmd.name = layer_name
        return self._kicad.send(cmd, board_commands_pb2.BoardLayerResponse).layer

    @overload
    def expand_text_variables(self, text: str) -> str:
        ...

    @overload
    def expand_text_variables(self, text: List[str]) -> List[str]:
        ...

    def expand_text_variables(self, text: Union[str, List[str]]) -> Union[str, List[str]]:
        """Expands text variables in a string or list of strings.  Any text variables that do not
        exist will be left as-is in the output."""
        command = project_commands_pb2.ExpandTextVariables()
        command.document.CopyFrom(self._doc)
        if isinstance(text, list):
            command.text.extend(text)
        else:
            command.text.append(text)
        response = self._kicad.send(command, project_commands_pb2.ExpandTextVariablesResponse)
        return (
            [text for text in response.text]
            if isinstance(text, list)
            else response.text[0]
            if len(response.text) > 0
            else ""
        )

    @overload
    def get_item_bounding_box(
        self, items: BoardItem, include_text: bool = False
    ) -> Optional[Box2]: ...

    @overload
    def get_item_bounding_box(
        self, items: Sequence[BoardItem], include_text: bool = False
    ) -> List[Optional[Box2]]: ...

    def get_item_bounding_box(
        self,
        items: Union[BoardItem, Sequence[BoardItem]],
        include_text: bool = False
    ) -> Union[Optional[Box2], List[Optional[Box2]]]:
        """Gets the KiCad-calculated bounding box for an item or items, returning None if the item
        does not exist or has no bounding box"""
        cmd = editor_commands_pb2.GetBoundingBox()
        cmd.header.document.CopyFrom(self._doc)
        cmd.mode = (
            editor_commands_pb2.BoundingBoxMode.BBM_ITEM_AND_CHILD_TEXT
            if include_text
            else editor_commands_pb2.BoundingBoxMode.BBM_ITEM_ONLY
        )

        if isinstance(items, BoardItem):
            cmd.items.append(items.id)
        else:
            cmd.items.extend([i.id for i in items])

        response = self._kicad.send(cmd, editor_commands_pb2.GetBoundingBoxResponse)

        if isinstance(items, BoardItem):
            return Box2.from_proto(response.boxes[0]) if len(response.boxes) == 1 else None

        item_to_bbox = {item.value: bbox for item, bbox in zip(response.items, response.boxes)}
        return [
            Box2.from_proto(box)
            for box in (item_to_bbox.get(item.id.value, None) for item in items)
            if box is not None
        ]

    @overload
    def get_pad_shapes_as_polygons(
        self, pads: Pad, layer: BoardLayer.ValueType = BoardLayer.BL_F_Cu
    ) -> Optional[PolygonWithHoles]: ...

    @overload
    def get_pad_shapes_as_polygons(
        self, pads: Sequence[Pad], layer: BoardLayer.ValueType = BoardLayer.BL_F_Cu
    ) -> List[Optional[PolygonWithHoles]]: ...

    def get_pad_shapes_as_polygons(
        self, pads: Union[Pad, Sequence[Pad]], layer: BoardLayer.ValueType = BoardLayer.BL_F_Cu
    ) -> Union[Optional[PolygonWithHoles], List[Optional[PolygonWithHoles]]]:
        """Retrieves the polygonal shape of one or more pads on a given layer.  If a pad does not
        exist or has no polygonal shape on the given layer, None will be returned for that pad."""
        cmd = board_commands_pb2.GetPadShapeAsPolygon()
        cmd.board.CopyFrom(self._doc)
        cmd.layer = layer

        if isinstance(pads, Pad):
            cmd.pads.append(pads.id)
        else:
            cmd.pads.extend([pad.id for pad in pads])

        response = self._kicad.send(cmd, board_commands_pb2.PadShapeAsPolygonResponse)

        if isinstance(pads, Pad):
            return PolygonWithHoles(response.polygons[0]) if len(response.polygons) == 1 else None

        pad_to_polygon = {pad.value: polygon for pad, polygon in zip(response.pads, response.polygons)}
        return [
            PolygonWithHoles(p)
            for p in (pad_to_polygon.get(pad.id.value, None) for pad in pads)
            if p is not None
        ]

    def check_padstack_presence_on_layers(
        self,
        items: Union[BoardItem, Iterable[BoardItem]],
        layers: Union[board_types_pb2.BoardLayer.ValueType, Iterable[board_types_pb2.BoardLayer.ValueType]]
    ) -> Dict[BoardItem, Dict[board_types_pb2.BoardLayer.ValueType, bool]]:
        """Checks if the given items with padstacks (pads or vias) have content on the given layers.

        :param items: The items to check (one or more pads or vias).
        :param layers: The layer or layers to check for padstack presence.
        :return: A dictionary mapping each item to a dictionary of layers and their presence on
                 the given layer.

        .. versionadded:: 0.4.0 with KiCad 9.0.3
        """
        cmd = board_commands_pb2.CheckPadstackPresenceOnLayers()
        cmd.board.CopyFrom(self._doc)

        items_map: Dict[str, BoardItem] = {}

        if isinstance(items, BoardItem):
            cmd.items.append(items.id)
            items_map[items.id.value] = items
        else:
            cmd.items.extend([item.id for item in items])
            items_map.update({item.id.value: item for item in items})

        if isinstance(layers, int):
            cmd.layers.append(layers)
        else:
            cmd.layers.extend(layers)

        response = self._kicad.send(cmd, board_commands_pb2.PadstackPresenceResponse)

        result: Dict[BoardItem, Dict[board_types_pb2.BoardLayer.ValueType, bool]] = {}
        for entry in response.entries:
            if entry.item.value not in items_map:
                continue

            item = items_map[entry.item.value]
            layer = entry.layer
            presence = entry.presence is board_commands_pb2.PadstackPresence.PSP_PRESENT

            if item not in result:
                result[item] = {}

            result[item][layer] = presence

        return result

    def interactive_move(self, items: Union[KIID, Iterable[KIID]]):
        """Initiates an interactive move operation on one or more items on the board.  The user
        will be able to move the items interactively in the KiCad editor.  This is a blocking
        operation; this function will return immediately but future API calls will return AS_BUSY
        until the interactive move is complete."""
        cmd = board_commands_pb2.InteractiveMoveItems()
        cmd.board.CopyFrom(self._doc)

        if isinstance(items, KIID):
            cmd.items.append(items)
        else:
            cmd.items.extend(items)

        self._kicad.send(cmd, Empty)

    def refill_zones(self, block=True, max_poll_seconds: float = 30.0,
                     poll_interval_seconds: float = 0.5):
        """Refills all zones on the board.  If block is True, this function will block until the
        refill operation is complete.  If block is False, this function will return immediately,
        and future API calls will return AS_BUSY until the refill operation is complete."""
        cmd = board_commands_pb2.RefillZones()
        cmd.board.CopyFrom(self._doc)
        self._kicad.send(cmd, Empty)

        if not block:
            return

        # Zone fill is a blocking operation that can block the entire event loop.
        # To hide this from API users somewhat, do an initial busy loop here
        sleeps = 0

        while sleeps < max_poll_seconds:
            sleep(poll_interval_seconds)
            try:
                self._kicad.send(Ping(), Empty)
            except IOError:
                # transport-layer timeout
                continue
            except ApiError as e:
                if e.code == ApiStatusCode.AS_BUSY:
                    continue
                else:
                    raise e
            break

    def hit_test(self, item: Item, position: Vector2, tolerance: int = 0) -> bool:
        """Performs a hit test on a board item at a given position"""
        cmd = HitTest()
        cmd.header.document.CopyFrom(self._doc)
        cmd.id.CopyFrom(item.id)
        cmd.position.CopyFrom(position.proto)
        cmd.tolerance = tolerance
        return self._kicad.send(cmd, HitTestResponse).result == HitTestResult.HTR_HIT

    def get_visible_layers(self) -> Sequence[board_types_pb2.BoardLayer.ValueType]:
        cmd = board_commands_pb2.GetVisibleLayers()
        cmd.board.CopyFrom(self._doc)
        response = self._kicad.send(cmd, board_commands_pb2.BoardLayers)
        return response.layers

    def set_visible_layers(self, layers: Sequence[board_types_pb2.BoardLayer.ValueType]):
        cmd = board_commands_pb2.SetVisibleLayers()
        cmd.board.CopyFrom(self._doc)
        cmd.layers.extend(layers)
        self._kicad.send(cmd, Empty)

    def get_active_layer(self) -> board_types_pb2.BoardLayer.ValueType:
        cmd = board_commands_pb2.GetActiveLayer()
        cmd.board.CopyFrom(self._doc)
        response = self._kicad.send(cmd, board_commands_pb2.BoardLayerResponse)
        return response.layer

    def set_active_layer(self, layer: board_types_pb2.BoardLayer.ValueType):
        cmd = board_commands_pb2.SetActiveLayer()
        cmd.board.CopyFrom(self._doc)
        cmd.layer = layer
        self._kicad.send(cmd, Empty)

    def get_editor_appearance_settings(self) -> BoardEditorAppearanceSettings:
        cmd = board_commands_pb2.GetBoardEditorAppearanceSettings()
        response = self._kicad.send(cmd, board_commands_pb2.BoardEditorAppearanceSettings)
        return BoardEditorAppearanceSettings(response)

    def set_editor_appearance_settings(self, settings: BoardEditorAppearanceSettings):
        cmd = board_commands_pb2.SetBoardEditorAppearanceSettings()
        cmd.settings.CopyFrom(settings.proto)
        self._kicad.send(cmd, Empty)
