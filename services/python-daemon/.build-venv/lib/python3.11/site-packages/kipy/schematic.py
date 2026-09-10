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

from typing import Iterable, List, Optional, Sequence, Union, cast

from google.protobuf.empty_pb2 import Empty

from kipy.client import KiCadClient
from kipy.common_types import Commit, PageSettings, TitleBlockInfo
from kipy.project import Project
from kipy.schematic_types import (
    Group,
    LocalLabel,
    SchematicGraphicShape,
    SchematicImage,
    SchematicItem,
    SchematicLine,
    SchematicNet,
    SchematicSymbolInstance,
    SchematicText,
    SchematicTextBox,
    SheetInstance,
    SheetSymbol,
    unwrap,
)
from kipy.proto.common.commands import editor_commands_pb2, project_commands_pb2
from kipy.proto.common.commands.editor_commands_pb2 import (
    BeginCommit,
    BeginCommitResponse,
    CommitAction,
    CreateItems,
    CreateItemsResponse,
    DeleteItems,
    DeleteItemsResponse,
    EndCommit,
    EndCommitResponse,
    GetItems,
    GetItemsById,
    GetItemsResponse,
    GetPageSettings,
    SetPageSettings,
    UpdateItems,
    UpdateItemsResponse,
)
from kipy.proto.common.types import (
    DocumentSpecifier,
    KIID,
    KiCadObjectType,
    base_types_pb2,
)
from kipy.proto.schematic.schematic_commands_pb2 import (
    GetSchematicHierarchy,
    GetSchematicNetlist,
    SchematicHierarchyResponse,
    SchematicNetlistResponse,
)
from kipy.util import pack_any
from kipy.wrapper import Wrapper


class Schematic:
    """
    .. versionadded:: 0.x.y (KiCad 11)
    """

    def __init__(self, kicad: KiCadClient, document: DocumentSpecifier):
        self._kicad = kicad
        self._doc = document

    def __repr__(self) -> str:
        return f"Schematic(filename={self.name}, path={self._doc.sheet_path})"

    @property
    def client(self) -> KiCadClient:
        return self._kicad

    @property
    def document(self) -> DocumentSpecifier:
        return self._doc

    def get_project(self) -> Project:
        return Project(self._kicad, self._doc)

    @property
    def name(self) -> str:
        return self._doc.project.name + ".kicad_sch"

    def save(self):
        command = project_commands_pb2.SaveDocument()
        command.document.CopyFrom(self._doc)
        self._kicad.send(command, Empty)

    def save_as(
        self, filename: str, overwrite: bool = False, include_project: bool = True
    ):
        command = editor_commands_pb2.SaveCopyOfDocument()
        command.document.CopyFrom(self._doc)
        command.path = filename
        command.options.overwrite = overwrite
        command.options.include_project = include_project
        self._kicad.send(command, Empty)

    def revert(self):
        command = editor_commands_pb2.RevertDocument()
        command.document.CopyFrom(self._doc)
        self._kicad.send(command, Empty)

    def begin_commit(self) -> Commit:
        command = BeginCommit()
        return Commit(self._kicad.send(command, BeginCommitResponse).id)

    def push_commit(self, commit: Commit, message: str = ""):
        command = EndCommit()
        command.id.CopyFrom(commit.id)
        command.action = CommitAction.CMA_COMMIT
        command.message = message
        self._kicad.send(command, EndCommitResponse)

    def drop_commit(self, commit: Commit):
        command = EndCommit()
        command.id.CopyFrom(commit.id)
        command.action = CommitAction.CMA_DROP
        self._kicad.send(command, EndCommitResponse)

    def create_items(
        self, items: Union[Wrapper, Iterable[Wrapper]]
    ) -> List[SchematicItem]:
        command = CreateItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, Wrapper):
            command.items.append(pack_any(items.proto))
        else:
            command.items.extend(pack_any(item.proto) for item in items)

        return [
            cast(SchematicItem, unwrap(result.item))
            for result in self._kicad.send(command, CreateItemsResponse).created_items
        ]

    def get_items(
        self,
        types: Union[KiCadObjectType.ValueType, Sequence[KiCadObjectType.ValueType]],
    ) -> Sequence[SchematicItem]:
        command = GetItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(types, int):
            command.types.append(types)
        else:
            command.types.extend(types)

        return [
            cast(SchematicItem, unwrap(item))
            for item in self._kicad.send(command, GetItemsResponse).items
        ]

    def get_items_by_id(
        self, ids: Union[KIID, Sequence[KIID]]
    ) -> Sequence[SchematicItem]:
        command = GetItemsById()
        command.header.document.CopyFrom(self._doc)

        if isinstance(ids, KIID):
            command.items.append(ids)
        else:
            command.items.extend(ids)

        return [
            cast(SchematicItem, unwrap(item))
            for item in self._kicad.send(command, GetItemsResponse).items
        ]

    def update_items(
        self, items: Union[SchematicItem, Sequence[SchematicItem]]
    ) -> List[SchematicItem]:
        command = UpdateItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, SchematicItem):
            command.items.append(pack_any(items.proto))
        else:
            command.items.extend(pack_any(item.proto) for item in items)

        if len(command.items) == 0:
            return []

        return [
            cast(SchematicItem, unwrap(result.item))
            for result in self._kicad.send(command, UpdateItemsResponse).updated_items
        ]

    def remove_items(self, items: Union[SchematicItem, Sequence[SchematicItem]]):
        command = DeleteItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, SchematicItem):
            command.item_ids.append(items.id)
        else:
            command.item_ids.extend(item.id for item in items)

        if len(command.item_ids) == 0:
            return

        self._kicad.send(command, DeleteItemsResponse)

    def remove_items_by_id(self, items: Union[KIID, Sequence[KIID]]):
        command = DeleteItems()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, KIID):
            command.item_ids.append(items)
        else:
            command.item_ids.extend(items)

        if len(command.item_ids) == 0:
            return

        self._kicad.send(command, DeleteItemsResponse)

    def get_lines(self) -> Sequence[SchematicLine]:
        return [
            cast(SchematicLine, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_SCH_LINE])
        ]

    def get_text(self) -> Sequence[Union[SchematicText, SchematicTextBox]]:
        return [
            cast(SchematicText, item)
            if isinstance(item, SchematicText)
            else cast(SchematicTextBox, item)
            for item in self.get_items(
                types=[KiCadObjectType.KOT_SCH_TEXT, KiCadObjectType.KOT_SCH_TEXTBOX]
            )
        ]

    def get_shapes(self) -> Sequence[SchematicGraphicShape]:
        return [
            cast(SchematicGraphicShape, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_SCH_SHAPE])
        ]

    def get_images(self) -> Sequence[SchematicImage]:
        return [
            cast(SchematicImage, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_SCH_BITMAP])
        ]

    def get_labels(self) -> Sequence[LocalLabel]:
        return [
            cast(LocalLabel, item)
            for item in self.get_items(
                types=[
                    KiCadObjectType.KOT_SCH_LABEL,
                    KiCadObjectType.KOT_SCH_GLOBAL_LABEL,
                    KiCadObjectType.KOT_SCH_HIER_LABEL,
                    KiCadObjectType.KOT_SCH_DIRECTIVE_LABEL,
                ]
            )
        ]

    def get_symbols(self) -> Sequence[SchematicSymbolInstance]:
        return [
            cast(SchematicSymbolInstance, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_SCH_SYMBOL])
        ]

    def get_sheet_symbols(self) -> Sequence[SheetSymbol]:
        return [
            cast(SheetSymbol, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_SCH_SHEET])
        ]

    def get_groups(self) -> Sequence[Group]:
        groups = [
            cast(Group, item)
            for item in self.get_items(types=[KiCadObjectType.KOT_SCH_GROUP])
        ]

        if len(groups) > 0:
            for group in groups:
                group._unwrapped_items = self.get_items_by_id(group._item_ids)

        return groups

    def get_hierarchy(self) -> list[SheetInstance]:
        command = GetSchematicHierarchy()
        command.document.CopyFrom(self._doc)
        response = self._kicad.send(command, SchematicHierarchyResponse)
        return [SheetInstance(proto=sheet) for sheet in response.top_level_sheets]

    def get_netlist(
        self,
        types: Union[
            KiCadObjectType.ValueType, Sequence[KiCadObjectType.ValueType], None
        ] = None,
    ) -> list[SchematicNet]:
        command = GetSchematicNetlist()
        command.document.CopyFrom(self._doc)

        if types is not None:
            if isinstance(types, int):
                command.types.append(types)
            else:
                command.types.extend(types)

        response = self._kicad.send(command, SchematicNetlistResponse)
        return [SchematicNet(proto=net) for net in response.nets]

    def get_title_block(self) -> TitleBlockInfo:
        command = editor_commands_pb2.GetTitleBlockInfo()
        command.document.CopyFrom(self._doc)
        return TitleBlockInfo(self._kicad.send(command, base_types_pb2.TitleBlockInfo))

    def set_title_block(self, title_block: TitleBlockInfo):
        command = editor_commands_pb2.SetTitleBlockInfo()
        command.document.CopyFrom(self._doc)
        command.title_block.CopyFrom(title_block.proto)
        self._kicad.send(command, Empty)

    def get_page_settings(self) -> PageSettings:
        command = GetPageSettings()
        command.document.CopyFrom(self._doc)
        return PageSettings(self._kicad.send(command, base_types_pb2.PageSettings))

    def set_page_settings(self, page_settings: PageSettings) -> PageSettings:
        command = SetPageSettings()
        command.document.CopyFrom(self._doc)
        command.page_settings.CopyFrom(page_settings.proto)
        return PageSettings(self._kicad.send(command, base_types_pb2.PageSettings))

    def get_as_string(self) -> str:
        command = editor_commands_pb2.SaveDocumentToString()
        command.document.CopyFrom(self._doc)
        return self._kicad.send(
            command, editor_commands_pb2.SavedDocumentResponse
        ).contents

    def get_selection_as_string(self) -> str:
        command = editor_commands_pb2.SaveSelectionToString()
        return self._kicad.send(
            command, editor_commands_pb2.SavedSelectionResponse
        ).contents

    def get_selection(
        self,
        types: Optional[
            Union[KiCadObjectType.ValueType, Sequence[KiCadObjectType.ValueType]]
        ] = None,
    ) -> Sequence[SchematicItem]:
        command = editor_commands_pb2.GetSelection()
        command.header.document.CopyFrom(self._doc)

        if isinstance(types, int):
            command.types.append(types)
        else:
            command.types.extend(types or [])

        return [
            cast(SchematicItem, unwrap(item))
            for item in self._kicad.send(
                command, editor_commands_pb2.SelectionResponse
            ).items
        ]

    def add_to_selection(
        self, items: Union[SchematicItem, Sequence[SchematicItem]]
    ) -> Sequence[SchematicItem]:
        command = editor_commands_pb2.AddToSelection()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, SchematicItem):
            command.items.append(items.id)
        else:
            command.items.extend(item.id for item in items)

        return [
            cast(SchematicItem, unwrap(item))
            for item in self._kicad.send(
                command, editor_commands_pb2.SelectionResponse
            ).items
        ]

    def remove_from_selection(
        self, items: Union[SchematicItem, Sequence[SchematicItem]]
    ) -> Sequence[SchematicItem]:
        command = editor_commands_pb2.RemoveFromSelection()
        command.header.document.CopyFrom(self._doc)

        if isinstance(items, SchematicItem):
            command.items.append(items.id)
        else:
            command.items.extend(item.id for item in items)

        return [
            cast(SchematicItem, unwrap(item))
            for item in self._kicad.send(
                command, editor_commands_pb2.SelectionResponse
            ).items
        ]

    def clear_selection(self):
        command = editor_commands_pb2.ClearSelection()
        command.header.document.CopyFrom(self._doc)
        self._kicad.send(command, Empty)
