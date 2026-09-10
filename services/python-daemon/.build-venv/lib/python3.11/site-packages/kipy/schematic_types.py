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

from typing import Dict, Optional, Sequence

from google.protobuf.any_pb2 import Any
from google.protobuf.message import Message

from kipy.common_types import (
    Color,
    GraphicFillAttributes,
    GraphicAttributes,
    GraphicShape,
    LibraryIdentifier,
    SheetPath,
    StrokeAttributes,
    Text,
    TextBox,
    to_concrete_shape,
)
from kipy.geometry import Vector2
from kipy.proto.common.types import KIID
from kipy.proto.common.types.base_types_pb2 import ElectricalPinType, LockedState
from kipy.proto.schematic import schematic_types_pb2
from kipy.util import unpack_any
from kipy.wrapper import Item, Wrapper

from kipy.proto.schematic.schematic_types_pb2 import (  # noqa
    BusEntryType,
    SchematicLabelShape,
    SchematicLabelSpinStyle,
    SchematicLineType,
    SchematicPinOrientation,
    SchematicPinShape,
    SchematicSymbolOrientation,
    SchematicSymbolType,
    SheetSide,
)


class SchematicItem(Item):
    @property
    def id(self) -> KIID:
        return self.proto.id


class SchematicField(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicField] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicField] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SchematicField()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:
        return (
            f"SchematicField({self.name}={self.text.value}, pos={self.text.position})"
        )

    @property
    def name(self) -> str:
        return self._proto.name

    @name.setter
    def name(self, value: str):
        self._proto.name = value

    @property
    def text(self) -> Text:
        return Text(proto_ref=self._proto.text)

    @text.setter
    def text(self, value: Text):
        self._proto.text.CopyFrom(value.proto)

    @property
    def visible(self) -> bool:
        return self._proto.visible

    @visible.setter
    def visible(self, value: bool):
        self._proto.visible = value

    @property
    def show_name(self) -> bool:
        return self._proto.show_name

    @show_name.setter
    def show_name(self, value: bool):
        self._proto.show_name = value

    @property
    def allow_auto_place(self) -> bool:
        return self._proto.allow_auto_place

    @allow_auto_place.setter
    def allow_auto_place(self, value: bool):
        self._proto.allow_auto_place = value

    @property
    def is_private(self) -> bool:
        return self._proto.is_private

    @is_private.setter
    def is_private(self, value: bool):
        self._proto.is_private = value


class SchematicLine(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicLine] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicLine] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SchematicLine()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def start(self) -> Vector2:
        return Vector2(self._proto.start)

    @start.setter
    def start(self, value: Vector2):
        self._proto.start.CopyFrom(value.proto)

    @property
    def end(self) -> Vector2:
        return Vector2(self._proto.end)

    @end.setter
    def end(self, value: Vector2):
        self._proto.end.CopyFrom(value.proto)

    @property
    def type(self) -> SchematicLineType.ValueType:
        return self._proto.type

    @type.setter
    def type(self, value: SchematicLineType.ValueType):
        self._proto.type = value

    @property
    def stroke(self) -> StrokeAttributes:
        return StrokeAttributes(proto_ref=self._proto.stroke)

    @stroke.setter
    def stroke(self, value: StrokeAttributes):
        self._proto.stroke.CopyFrom(value.proto)


class Junction(SchematicItem):
    """
    Note: junctions in KiCad are computed dynamically based on line intersections.

    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.Junction] = None,
        proto_ref: Optional[schematic_types_pb2.Junction] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.Junction()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def position(self) -> Vector2:
        return Vector2(self._proto.position)

    @position.setter
    def position(self, value: Vector2):
        self._proto.position.CopyFrom(value.proto)

    @property
    def diameter(self) -> int:
        return self._proto.diameter.value_nm

    @diameter.setter
    def diameter(self, value: int):
        self._proto.diameter.value_nm = value

    @property
    def color(self) -> Color:
        return Color(proto_ref=self._proto.color)

    @color.setter
    def color(self, value: Color):
        self._proto.color.CopyFrom(value.proto)


class NoConnectMarker(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.NoConnectMarker] = None,
        proto_ref: Optional[schematic_types_pb2.NoConnectMarker] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.NoConnectMarker()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def position(self) -> Vector2:
        return Vector2(self._proto.position)

    @position.setter
    def position(self, value: Vector2):
        self._proto.position.CopyFrom(value.proto)

    @property
    def size(self) -> int:
        return self._proto.size.value_nm

    @size.setter
    def size(self, value: int):
        self._proto.size.value_nm = value


class BusEntry(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.BusEntry] = None,
        proto_ref: Optional[schematic_types_pb2.BusEntry] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.BusEntry()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def position(self) -> Vector2:
        return Vector2(self._proto.position)

    @position.setter
    def position(self, value: Vector2):
        self._proto.position.CopyFrom(value.proto)

    @property
    def size(self) -> Vector2:
        return Vector2(self._proto.size)

    @size.setter
    def size(self, value: Vector2):
        self._proto.size.CopyFrom(value.proto)

    @property
    def stroke(self) -> StrokeAttributes:
        return StrokeAttributes(proto_ref=self._proto.stroke)

    @stroke.setter
    def stroke(self, value: StrokeAttributes):
        self._proto.stroke.CopyFrom(value.proto)

    @property
    def type(self) -> BusEntryType.ValueType:
        return self._proto.type

    @type.setter
    def type(self, value: BusEntryType.ValueType):
        self._proto.type = value


class SchematicText(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicText] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicText] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SchematicText()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def text(self) -> Text:
        return Text(proto_ref=self._proto.text)

    @text.setter
    def text(self, value: Text):
        self._proto.text.CopyFrom(value.proto)

    @property
    def position(self) -> Vector2:
        return Vector2(self._proto.text.position)

    @position.setter
    def position(self, value: Vector2):
        self._proto.text.position.CopyFrom(value.proto)

    @property
    def value(self) -> str:
        return self._proto.text.text

    @value.setter
    def value(self, value: str):
        self._proto.text.text = value

    @property
    def exclude_from_sim(self) -> bool:
        return self._proto.exclude_from_sim

    @exclude_from_sim.setter
    def exclude_from_sim(self, value: bool):
        self._proto.exclude_from_sim = value


class SchematicTextBox(SchematicItem):
    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicTextBox] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicTextBox] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicTextBox()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def textbox(self) -> TextBox:
        return TextBox(proto_ref=self._proto.textbox)

    @textbox.setter
    def textbox(self, value: TextBox):
        self._proto.textbox.CopyFrom(value.proto)

    @property
    def top_left(self) -> Vector2:
        return Vector2(self._proto.textbox.top_left)

    @top_left.setter
    def top_left(self, value: Vector2):
        self._proto.textbox.top_left.CopyFrom(value.proto)

    @property
    def bottom_right(self) -> Vector2:
        return Vector2(self._proto.textbox.bottom_right)

    @bottom_right.setter
    def bottom_right(self, value: Vector2):
        self._proto.textbox.bottom_right.CopyFrom(value.proto)

    @property
    def value(self) -> str:
        return self._proto.textbox.text

    @value.setter
    def value(self, value: str):
        self._proto.textbox.text = value

    @property
    def graphic_attributes(self) -> GraphicAttributes:
        return GraphicAttributes(proto_ref=self._proto.graphic_attributes)

    @graphic_attributes.setter
    def graphic_attributes(self, value: GraphicAttributes):
        self._proto.graphic_attributes.CopyFrom(value.proto)

    @property
    def exclude_from_sim(self) -> bool:
        return self._proto.exclude_from_sim

    @exclude_from_sim.setter
    def exclude_from_sim(self, value: bool):
        self._proto.exclude_from_sim = value

    @property
    def margin_left(self) -> int:
        return self._proto.margin_left.value_nm

    @margin_left.setter
    def margin_left(self, value: int):
        self._proto.margin_left.value_nm = value

    @property
    def margin_top(self) -> int:
        return self._proto.margin_top.value_nm

    @margin_top.setter
    def margin_top(self, value: int):
        self._proto.margin_top.value_nm = value

    @property
    def margin_right(self) -> int:
        return self._proto.margin_right.value_nm

    @margin_right.setter
    def margin_right(self, value: int):
        self._proto.margin_right.value_nm = value

    @property
    def margin_bottom(self) -> int:
        return self._proto.margin_bottom.value_nm

    @margin_bottom.setter
    def margin_bottom(self, value: int):
        self._proto.margin_bottom.value_nm = value


class SchematicGraphicShape(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicGraphicShape] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicGraphicShape] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicGraphicShape()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def shape(self) -> Optional[GraphicShape]:
        return to_concrete_shape(GraphicShape(self._proto.shape))

    @shape.setter
    def shape(self, value: GraphicShape):
        if value._graphic_proto.WhichOneof("geometry") == "segment":
            raise ValueError(
                "SchematicGraphicShape cannot be a segment; use SchematicLine instead"
            )
        self._proto.shape.CopyFrom(value._graphic_proto)


class SchematicImage(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicImage] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicImage] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SchematicImage()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def position(self) -> Vector2:
        return Vector2(self._proto.position)

    @position.setter
    def position(self, value: Vector2):
        self._proto.position.CopyFrom(value.proto)

    @property
    def transform_origin_offset(self) -> Vector2:
        return Vector2(self._proto.transform_origin_offset)

    @transform_origin_offset.setter
    def transform_origin_offset(self, value: Vector2):
        self._proto.transform_origin_offset.CopyFrom(value.proto)

    @property
    def image_scale(self) -> float:
        return self._proto.image_scale.value

    @image_scale.setter
    def image_scale(self, value: float):
        self._proto.image_scale.value = value

    @property
    def image_data(self) -> bytes:
        return self._proto.image_data

    @image_data.setter
    def image_data(self, value: bytes):
        self._proto.image_data = value


class BaseLabel(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    @property
    def locked(self) -> bool:
        return self.proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self.proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def position(self) -> Vector2:
        return Vector2(self.proto.position)

    @position.setter
    def position(self, value: Vector2):
        self.proto.position.CopyFrom(value.proto)

    @property
    def text(self) -> Text:
        return Text(proto_ref=self.proto.text)

    @text.setter
    def text(self, value: Text):
        self.proto.text.CopyFrom(value.proto)

    @property
    def spin_style(self) -> SchematicLabelSpinStyle.ValueType:
        return self.proto.spin_style

    @spin_style.setter
    def spin_style(self, value: SchematicLabelSpinStyle.ValueType):
        self.proto.spin_style = value

    @property
    def fields(self) -> Sequence[SchematicField]:
        return [SchematicField(proto_ref=field) for field in self.proto.fields]

    @fields.setter
    def fields(self, value: Sequence[SchematicField]):
        del self.proto.fields[:]
        self.proto.fields.extend(field.proto for field in value)


class ShapeLabel(BaseLabel):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    @property
    def shape(self) -> SchematicLabelShape.ValueType:
        return self.proto.shape

    @shape.setter
    def shape(self, value: SchematicLabelShape.ValueType):
        self.proto.shape = value


class LocalLabel(BaseLabel):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.LocalLabel] = None,
        proto_ref: Optional[schematic_types_pb2.LocalLabel] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.LocalLabel()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)


class GlobalLabel(ShapeLabel):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.GlobalLabel] = None,
        proto_ref: Optional[schematic_types_pb2.GlobalLabel] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.GlobalLabel()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def intersheet_refs_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.intersheet_refs_field)

    @intersheet_refs_field.setter
    def intersheet_refs_field(self, value: SchematicField):
        self._proto.intersheet_refs_field.CopyFrom(value.proto)


class HierarchicalLabel(ShapeLabel):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.HierarchicalLabel] = None,
        proto_ref: Optional[schematic_types_pb2.HierarchicalLabel] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.HierarchicalLabel()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)


class DirectiveLabel(ShapeLabel):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.DirectiveLabel] = None,
        proto_ref: Optional[schematic_types_pb2.DirectiveLabel] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.DirectiveLabel()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)


class Group(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.Group] = None,
        proto_ref: Optional[schematic_types_pb2.Group] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.Group()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

        self._item_ids = self._proto.items
        self._unwrapped_items: Optional[Sequence[SchematicItem]] = None

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def name(self) -> str:
        return self._proto.name

    @name.setter
    def name(self, value: str):
        self._proto.name = value

    @property
    def items(self) -> Sequence[SchematicItem]:
        return self._unwrapped_items if self._unwrapped_items is not None else []

    @items.setter
    def items(self, value: Sequence[SchematicItem]):
        del self._proto.items[:]
        self._unwrapped_items = value
        for item in value:
            self._proto.items.append(item.id)


class SheetPin(ShapeLabel):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SheetPin] = None,
        proto_ref: Optional[schematic_types_pb2.SheetPin] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SheetPin()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:
        return f"SheetPin({self.text.value}, pos={self.position})"

    @property
    def side(self) -> SheetSide.ValueType:
        return self._proto.side

    @side.setter
    def side(self, value: SheetSide.ValueType):
        self._proto.side = value


class SheetSymbol(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SheetSymbol] = None,
        proto_ref: Optional[schematic_types_pb2.SheetSymbol] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SheetSymbol()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:
        return f"SheetSymbol(name={self.name_field.text.value}, file={self.filename_field.text.value}, pos={self.position})"

    @property
    def path(self) -> SheetPath:
        return SheetPath(self._proto.path)

    @path.setter
    def path(self, path: SheetPath):
        self._proto.path.CopyFrom(path.proto)

    @property
    def page_number(self) -> str:
        return self._proto.page_number

    @page_number.setter
    def page_number(self, page_number: str):
        self._proto.page_number = page_number

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def position(self) -> Vector2:
        return Vector2(self._proto.position)

    @position.setter
    def position(self, value: Vector2):
        self._proto.position.CopyFrom(value.proto)

    @property
    def size(self) -> Vector2:
        return Vector2(self._proto.size)

    @size.setter
    def size(self, value: Vector2):
        self._proto.size.CopyFrom(value.proto)

    @property
    def border_stroke(self) -> StrokeAttributes:
        return StrokeAttributes(proto_ref=self._proto.border_stroke)

    @border_stroke.setter
    def border_stroke(self, value: StrokeAttributes):
        self._proto.border_stroke.CopyFrom(value.proto)

    @property
    def fill(self) -> GraphicFillAttributes:
        return GraphicFillAttributes(proto_ref=self._proto.fill)

    @fill.setter
    def fill(self, value: GraphicFillAttributes):
        self._proto.fill.CopyFrom(value.proto)

    @property
    def name_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.name_field)

    @name_field.setter
    def name_field(self, value: SchematicField):
        self._proto.name_field.CopyFrom(value.proto)

    @property
    def filename_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.filename_field)

    @filename_field.setter
    def filename_field(self, value: SchematicField):
        self._proto.filename_field.CopyFrom(value.proto)

    @property
    def user_fields(self) -> Sequence[SchematicField]:
        return [SchematicField(proto_ref=field) for field in self._proto.user_fields]

    @user_fields.setter
    def user_fields(self, value: Sequence[SchematicField]):
        del self._proto.user_fields[:]
        self._proto.user_fields.extend(field.proto for field in value)

    @property
    def pins(self) -> Sequence[SheetPin]:
        return [SheetPin(proto_ref=pin) for pin in self._proto.pins]

    @pins.setter
    def pins(self, value: Sequence[SheetPin]):
        del self._proto.pins[:]
        self._proto.pins.extend(pin.proto for pin in value)

    @property
    def exclude_from_sim(self) -> bool:
        return self._proto.exclude_from_sim

    @exclude_from_sim.setter
    def exclude_from_sim(self, value: bool):
        self._proto.exclude_from_sim = value

    @property
    def exclude_from_bom(self) -> bool:
        return self._proto.exclude_from_bom

    @exclude_from_bom.setter
    def exclude_from_bom(self, value: bool):
        self._proto.exclude_from_bom = value

    @property
    def exclude_from_board(self) -> bool:
        return self._proto.exclude_from_board

    @exclude_from_board.setter
    def exclude_from_board(self, value: bool):
        self._proto.exclude_from_board = value

    @property
    def dnp(self) -> bool:
        return self._proto.dnp

    @dnp.setter
    def dnp(self, value: bool):
        self._proto.dnp = value


class SchematicPinAlternate(Wrapper):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicPinAlternate] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicPinAlternate] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicPinAlternate()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def name(self) -> str:
        return self._proto.name

    @name.setter
    def name(self, value: str):
        self._proto.name = value

    @property
    def shape(self) -> SchematicPinShape.ValueType:
        return self._proto.shape

    @shape.setter
    def shape(self, value: SchematicPinShape.ValueType):
        self._proto.shape = value

    @property
    def electrical_type(self) -> ElectricalPinType.ValueType:
        return self._proto.electrical_type

    @electrical_type.setter
    def electrical_type(self, value: ElectricalPinType.ValueType):
        self._proto.electrical_type = value


class SchematicPin(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicPin] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicPin] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SchematicPin()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def name(self) -> str:
        return self._proto.name

    @name.setter
    def name(self, value: str):
        self._proto.name = value

    @property
    def number(self) -> str:
        return self._proto.number

    @number.setter
    def number(self, value: str):
        self._proto.number = value

    @property
    def position(self) -> Vector2:
        return Vector2(self._proto.position)

    @position.setter
    def position(self, value: Vector2):
        self._proto.position.CopyFrom(value.proto)

    @property
    def length(self) -> int:
        return self._proto.length.value_nm

    @length.setter
    def length(self, value: int):
        self._proto.length.value_nm = value

    @property
    def orientation(self) -> SchematicPinOrientation.ValueType:
        return self._proto.orientation

    @orientation.setter
    def orientation(self, value: SchematicPinOrientation.ValueType):
        self._proto.orientation = value

    @property
    def electrical_type(self) -> ElectricalPinType.ValueType:
        return self._proto.electrical_type

    @electrical_type.setter
    def electrical_type(self, value: ElectricalPinType.ValueType):
        self._proto.electrical_type = value

    @property
    def shape(self) -> SchematicPinShape.ValueType:
        return self._proto.shape

    @shape.setter
    def shape(self, value: SchematicPinShape.ValueType):
        self._proto.shape = value

    @property
    def visible(self) -> bool:
        return self._proto.visible

    @visible.setter
    def visible(self, value: bool):
        self._proto.visible = value

    @property
    def name_text_size(self) -> int:
        return self._proto.name_text_size.value_nm

    @name_text_size.setter
    def name_text_size(self, value: int):
        self._proto.name_text_size.value_nm = value

    @property
    def number_text_size(self) -> int:
        return self._proto.number_text_size.value_nm

    @number_text_size.setter
    def number_text_size(self, value: int):
        self._proto.number_text_size.value_nm = value

    @property
    def alternates(self) -> Sequence[SchematicPinAlternate]:
        return [SchematicPinAlternate(proto_ref=alt) for alt in self._proto.alternates]

    @alternates.setter
    def alternates(self, value: Sequence[SchematicPinAlternate]):
        del self._proto.alternates[:]
        self._proto.alternates.extend(alt.proto for alt in value)

    @property
    def active_alternate(self) -> Optional[str]:
        return (
            self._proto.active_alternate
            if self._proto.HasField("active_alternate")
            else None
        )

    @active_alternate.setter
    def active_alternate(self, value: Optional[str]):
        if value is not None:
            self._proto.active_alternate = value
        else:
            self._proto.ClearField("active_alternate")


class SchematicSymbolChild(Wrapper):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicSymbolChild] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicSymbolChild] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicSymbolChild()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def item(self) -> Any:
        return self._proto.item

    @item.setter
    def item(self, value: Any):
        self._proto.item.CopyFrom(value)

    @property
    def unit(self) -> Optional[int]:
        return self._proto.unit.unit if self._proto.HasField("unit") else None

    @unit.setter
    def unit(self, value: Optional[int]):
        if value is not None:
            self._proto.unit.unit = value
        else:
            self._proto.ClearField("unit")

    @property
    def body_style(self) -> Optional[int]:
        return (
            self._proto.body_style.style if self._proto.HasField("body_style") else None
        )

    @body_style.setter
    def body_style(self, value: Optional[int]):
        if value is not None:
            self._proto.body_style.style = value
        else:
            self._proto.ClearField("body_style")

    @property
    def is_private(self) -> bool:
        return self._proto.is_private

    @is_private.setter
    def is_private(self, value: bool):
        self._proto.is_private = value


class SchematicSymbolAttributes(Wrapper):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicSymbolAttributes] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicSymbolAttributes] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicSymbolAttributes()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def exclude_from_simulation(self) -> bool:
        return self._proto.exclude_from_simulation

    @exclude_from_simulation.setter
    def exclude_from_simulation(self, value: bool):
        self._proto.exclude_from_simulation = value

    @property
    def exclude_from_bill_of_materials(self) -> bool:
        return self._proto.exclude_from_bill_of_materials

    @exclude_from_bill_of_materials.setter
    def exclude_from_bill_of_materials(self, value: bool):
        self._proto.exclude_from_bill_of_materials = value

    @property
    def exclude_from_board(self) -> bool:
        return self._proto.exclude_from_board

    @exclude_from_board.setter
    def exclude_from_board(self, value: bool):
        self._proto.exclude_from_board = value

    @property
    def exclude_from_position_files(self) -> bool:
        return self._proto.exclude_from_position_files

    @exclude_from_position_files.setter
    def exclude_from_position_files(self, value: bool):
        self._proto.exclude_from_position_files = value

    @property
    def do_not_populate(self) -> bool:
        return self._proto.do_not_populate

    @do_not_populate.setter
    def do_not_populate(self, value: bool):
        self._proto.do_not_populate = value


class SchematicSymbolVariant(Wrapper):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicSymbolVariant] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicSymbolVariant] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicSymbolVariant()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def name(self) -> str:
        return self._proto.name

    @name.setter
    def name(self, value: str):
        self._proto.name = value

    @property
    def description(self) -> str:
        return self._proto.description

    @description.setter
    def description(self, value: str):
        self._proto.description = value

    @property
    def attributes(self) -> SchematicSymbolAttributes:
        return SchematicSymbolAttributes(proto_ref=self._proto.attributes)

    @attributes.setter
    def attributes(self, value: SchematicSymbolAttributes):
        self._proto.attributes.CopyFrom(value.proto)

    @property
    def fields(self) -> Dict[str, str]:
        return dict(self._proto.fields)

    @fields.setter
    def fields(self, value: Dict[str, str]):
        self._proto.fields.clear()
        self._proto.fields.update(value)


class SchematicSymbol(Wrapper):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicSymbol] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicSymbol] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicSymbol()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def id(self) -> LibraryIdentifier:
        return LibraryIdentifier(proto_ref=self._proto.id)

    @id.setter
    def id(self, value: LibraryIdentifier):
        self._proto.id.CopyFrom(value.proto)

    @property
    def type(self) -> SchematicSymbolType.ValueType:
        return self._proto.type

    @type.setter
    def type(self, value: SchematicSymbolType.ValueType):
        self._proto.type = value

    @property
    def attributes(self) -> SchematicSymbolAttributes:
        return SchematicSymbolAttributes(proto_ref=self._proto.attributes)

    @attributes.setter
    def attributes(self, value: SchematicSymbolAttributes):
        self._proto.attributes.CopyFrom(value.proto)

    @property
    def reference_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.reference_field)

    @reference_field.setter
    def reference_field(self, value: SchematicField):
        self._proto.reference_field.CopyFrom(value.proto)

    @property
    def value_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.value_field)

    @value_field.setter
    def value_field(self, value: SchematicField):
        self._proto.value_field.CopyFrom(value.proto)

    @property
    def footprint_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.footprint_field)

    @footprint_field.setter
    def footprint_field(self, value: SchematicField):
        self._proto.footprint_field.CopyFrom(value.proto)

    @property
    def datasheet_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.datasheet_field)

    @datasheet_field.setter
    def datasheet_field(self, value: SchematicField):
        self._proto.datasheet_field.CopyFrom(value.proto)

    @property
    def description_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.description_field)

    @description_field.setter
    def description_field(self, value: SchematicField):
        self._proto.description_field.CopyFrom(value.proto)

    @property
    def items(self) -> Sequence[SchematicSymbolChild]:
        return [SchematicSymbolChild(proto_ref=item) for item in self._proto.items]

    @items.setter
    def items(self, value: Sequence[SchematicSymbolChild]):
        del self._proto.items[:]
        self._proto.items.extend(item.proto for item in value)

    @property
    def unit_count(self) -> int:
        return self._proto.unit_count

    @unit_count.setter
    def unit_count(self, value: int):
        self._proto.unit_count = value

    @property
    def body_style_count(self) -> int:
        return self._proto.body_style_count

    @body_style_count.setter
    def body_style_count(self, value: int):
        self._proto.body_style_count = value

    @property
    def keywords(self) -> str:
        return self._proto.keywords

    @keywords.setter
    def keywords(self, value: str):
        self._proto.keywords = value

    @property
    def footprint_filters(self) -> Sequence[str]:
        return list(self._proto.footprint_filters)

    @footprint_filters.setter
    def footprint_filters(self, value: Sequence[str]):
        del self._proto.footprint_filters[:]
        self._proto.footprint_filters.extend(value)


class SchematicSymbolTransform(Wrapper):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicSymbolTransform] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicSymbolTransform] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicSymbolTransform()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def orientation(self) -> SchematicSymbolOrientation.ValueType:
        return self._proto.orientation

    @orientation.setter
    def orientation(self, value: SchematicSymbolOrientation.ValueType):
        self._proto.orientation = value

    @property
    def mirror_x(self) -> bool:
        return self._proto.mirror_x

    @mirror_x.setter
    def mirror_x(self, value: bool):
        self._proto.mirror_x = value

    @property
    def mirror_y(self) -> bool:
        return self._proto.mirror_y

    @mirror_y.setter
    def mirror_y(self, value: bool):
        self._proto.mirror_y = value


class SchematicSymbolInstance(SchematicItem):
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicSymbolInstance] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicSymbolInstance] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicSymbolInstance()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    @property
    def path(self) -> SheetPath:
        return SheetPath(proto_ref=self._proto.path)

    @path.setter
    def path(self, value: SheetPath):
        self._proto.path.CopyFrom(value.proto)

    @property
    def position(self) -> Vector2:
        return Vector2(self._proto.position)

    @position.setter
    def position(self, value: Vector2):
        self._proto.position.CopyFrom(value.proto)

    @property
    def transform(self) -> SchematicSymbolTransform:
        return SchematicSymbolTransform(proto_ref=self._proto.transform)

    @transform.setter
    def transform(self, value: SchematicSymbolTransform):
        self._proto.transform.CopyFrom(value.proto)

    @property
    def locked(self) -> bool:
        return self._proto.locked == LockedState.LS_LOCKED

    @locked.setter
    def locked(self, locked: bool):
        self._proto.locked = {
            True: LockedState.LS_LOCKED,
            False: LockedState.LS_UNLOCKED,
        }.get(locked, LockedState.LS_UNLOCKED)

    @property
    def definition(self) -> SchematicSymbol:
        return SchematicSymbol(proto_ref=self._proto.definition)

    @definition.setter
    def definition(self, value: SchematicSymbol):
        self._proto.definition.CopyFrom(value.proto)

    @property
    def reference_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.reference_field)

    @reference_field.setter
    def reference_field(self, value: SchematicField):
        self._proto.reference_field.CopyFrom(value.proto)

    @property
    def value_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.value_field)

    @value_field.setter
    def value_field(self, value: SchematicField):
        self._proto.value_field.CopyFrom(value.proto)

    @property
    def footprint_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.footprint_field)

    @footprint_field.setter
    def footprint_field(self, value: SchematicField):
        self._proto.footprint_field.CopyFrom(value.proto)

    @property
    def datasheet_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.datasheet_field)

    @datasheet_field.setter
    def datasheet_field(self, value: SchematicField):
        self._proto.datasheet_field.CopyFrom(value.proto)

    @property
    def description_field(self) -> SchematicField:
        return SchematicField(proto_ref=self._proto.description_field)

    @description_field.setter
    def description_field(self, value: SchematicField):
        self._proto.description_field.CopyFrom(value.proto)

    @property
    def attributes(self) -> SchematicSymbolAttributes:
        return SchematicSymbolAttributes(proto_ref=self._proto.attributes)

    @attributes.setter
    def attributes(self, value: SchematicSymbolAttributes):
        self._proto.attributes.CopyFrom(value.proto)

    @property
    def unit(self) -> int:
        return self._proto.unit.unit

    @unit.setter
    def unit(self, value: int):
        self._proto.unit.unit = value

    @property
    def body_style(self) -> Optional[int]:
        return (
            self._proto.body_style.style if self._proto.HasField("body_style") else None
        )

    @body_style.setter
    def body_style(self, value: Optional[int]):
        if value is not None:
            self._proto.body_style.style = value
        else:
            self._proto.ClearField("body_style")

    @property
    def show_pin_names(self) -> bool:
        return self._proto.show_pin_names

    @show_pin_names.setter
    def show_pin_names(self, value: bool):
        self._proto.show_pin_names = value

    @property
    def show_pin_numbers(self) -> bool:
        return self._proto.show_pin_numbers

    @show_pin_numbers.setter
    def show_pin_numbers(self, value: bool):
        self._proto.show_pin_numbers = value

    @property
    def pin_name_offset(self) -> int:
        return self._proto.pin_name_offset.value_nm

    @pin_name_offset.setter
    def pin_name_offset(self, value: int):
        self._proto.pin_name_offset.value_nm = value

    @property
    def variants(self) -> Sequence[SchematicSymbolVariant]:
        return [SchematicSymbolVariant(proto_ref=v) for v in self._proto.variants]

    @variants.setter
    def variants(self, value: Sequence[SchematicSymbolVariant]):
        del self._proto.variants[:]
        self._proto.variants.extend(v.proto for v in value)

    @property
    def user_fields(self) -> Sequence[SchematicField]:
        return [SchematicField(proto_ref=f) for f in self._proto.user_fields]

    @user_fields.setter
    def user_fields(self, value: Sequence[SchematicField]):
        del self._proto.user_fields[:]
        self._proto.user_fields.extend(f.proto for f in value)


class SheetInstance(Wrapper):
    """
    Data returned from e.g. GetSchematicHierarchy (read-only)

    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SheetInstance] = None,
        proto_ref: Optional[schematic_types_pb2.SheetInstance] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SheetInstance()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:

        def repr_child(c: SheetInstance, d: int):
            r = f"{'  ' * d}SheetInstance([{c.page_number}] {c.name} ({c.filename}))"

            if len(c.children) > 0:
                r += "\n"
                r += "\n".join([repr_child(child, d + 1) for child in c.children])

            return r

        if len(self.children) > 0:
            return repr_child(self, 0)

        return f"SheetInstance({self.name} [{self.page_number}] ({self.filename}))"

    @property
    def path(self) -> SheetPath:
        return SheetPath(proto_ref=self._proto.path)

    @property
    def name(self) -> str:
        return self._proto.name

    @property
    def filename(self) -> str:
        return self._proto.filename

    @property
    def page_number(self) -> str:
        return self._proto.page_number

    @property
    def children(self) -> Sequence["SheetInstance"]:
        return [SheetInstance(proto_ref=child) for child in self._proto.children]


class SchematicNetSheetContents(Wrapper):
    """
    Data returned from GetSchematicNetlist (read-only)

    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicNetSheetContents] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicNetSheetContents] = None,
    ):
        self._proto = (
            proto_ref
            if proto_ref is not None
            else schematic_types_pb2.SchematicNetSheetContents()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:
        return f"SchematicNetSheetContents({self.path}, {len(self.items)} items)"

    @property
    def path(self) -> SheetPath:
        return SheetPath(proto_ref=self._proto.path)

    @property
    def items(self) -> list[KIID]:
        return list(self._proto.items)


class SchematicNet(Wrapper):
    """
    Data returned from e.g. GetSchematicNetlist (read-only)

    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(
        self,
        proto: Optional[schematic_types_pb2.SchematicNet] = None,
        proto_ref: Optional[schematic_types_pb2.SchematicNet] = None,
    ):
        self._proto = (
            proto_ref if proto_ref is not None else schematic_types_pb2.SchematicNet()
        )

        if proto is not None:
            self._proto.CopyFrom(proto)

    def __repr__(self) -> str:

        def repr_sheet(s: SchematicNetSheetContents, d: int):
            return f"{'  ' * d}{s.path} ({len(s.items)} items)"

        r = f"SchematicNet({self.name})"

        if len(self.sheets) > 0:
            r += "\n"
            r += "\n".join([repr_sheet(sheet, 1) for sheet in self.sheets])

        return r

    @property
    def name(self) -> str:
        return self._proto.name

    @property
    def sheets(self) -> Sequence[SchematicNetSheetContents]:
        return [SchematicNetSheetContents(proto_ref=s) for s in self._proto.sheets]


_proto_to_object: Dict[type[Message], type[Wrapper]] = {
    schematic_types_pb2.SchematicField: SchematicField,
    schematic_types_pb2.SchematicLine: SchematicLine,
    schematic_types_pb2.Junction: Junction,
    schematic_types_pb2.NoConnectMarker: NoConnectMarker,
    schematic_types_pb2.BusEntry: BusEntry,
    schematic_types_pb2.SchematicText: SchematicText,
    schematic_types_pb2.SchematicTextBox: SchematicTextBox,
    schematic_types_pb2.SchematicGraphicShape: SchematicGraphicShape,
    schematic_types_pb2.SchematicImage: SchematicImage,
    schematic_types_pb2.LocalLabel: LocalLabel,
    schematic_types_pb2.GlobalLabel: GlobalLabel,
    schematic_types_pb2.HierarchicalLabel: HierarchicalLabel,
    schematic_types_pb2.DirectiveLabel: DirectiveLabel,
    schematic_types_pb2.Group: Group,
    schematic_types_pb2.SheetPin: SheetPin,
    schematic_types_pb2.SheetSymbol: SheetSymbol,
    schematic_types_pb2.SchematicPin: SchematicPin,
    schematic_types_pb2.SchematicSymbolInstance: SchematicSymbolInstance,
}


def unwrap(message: Any) -> Wrapper:
    concrete = unpack_any(message)
    wrapper = _proto_to_object.get(type(concrete), None)
    assert wrapper is not None
    return wrapper(proto=concrete)
