"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 6, '', 'common/types/base_types.proto')
_sym_db = _symbol_database.Default()
from google.protobuf import field_mask_pb2 as google_dot_protobuf_dot_field__mask__pb2
from ...common.types import enums_pb2 as common_dot_types_dot_enums__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1dcommon/types/base_types.proto\x12\x12kiapi.common.types\x1a google/protobuf/field_mask.proto\x1a\x18common/types/enums.proto"J\n\x15CommandStatusResponse\x121\n\x06status\x18\x01 \x01(\x0e2!.kiapi.common.types.CommandStatus"Q\n\x0cKiCadVersion\x12\r\n\x05major\x18\x01 \x01(\r\x12\r\n\x05minor\x18\x02 \x01(\r\x12\r\n\x05patch\x18\x03 \x01(\r\x12\x14\n\x0cfull_version\x18\x04 \x01(\t"\x15\n\x04KIID\x12\r\n\x05value\x18\x01 \x01(\t"A\n\x11LibraryIdentifier\x12\x18\n\x10library_nickname\x18\x01 \x01(\t\x12\x12\n\nentry_name\x18\x02 \x01(\t"P\n\tSheetPath\x12&\n\x04path\x18\x01 \x03(\x0b2\x18.kiapi.common.types.KIID\x12\x1b\n\x13path_human_readable\x18\x02 \x01(\t".\n\x10ProjectSpecifier\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0c\n\x04path\x18\x02 \x01(\t"\x90\x02\n\x11DocumentSpecifier\x12.\n\x04type\x18\x01 \x01(\x0e2 .kiapi.common.types.DocumentType\x127\n\x06lib_id\x18\x02 \x01(\x0b2%.kiapi.common.types.LibraryIdentifierH\x00\x123\n\nsheet_path\x18\x03 \x01(\x0b2\x1d.kiapi.common.types.SheetPathH\x00\x12\x18\n\x0eboard_filename\x18\x04 \x01(\tH\x00\x125\n\x07project\x18\x05 \x01(\x0b2$.kiapi.common.types.ProjectSpecifierB\x0c\n\nidentifier"\xa2\x01\n\nItemHeader\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier\x12+\n\tcontainer\x18\x02 \x01(\x0b2\x18.kiapi.common.types.KIID\x12.\n\nfield_mask\x18\x03 \x01(\x0b2\x1a.google.protobuf.FieldMask"%\n\x07Vector2\x12\x0c\n\x04x_nm\x18\x01 \x01(\x03\x12\x0c\n\x04y_nm\x18\x02 \x01(\x03"3\n\x07Vector3\x12\x0c\n\x04x_nm\x18\x01 \x01(\x03\x12\x0c\n\x04y_nm\x18\x02 \x01(\x03\x12\x0c\n\x04z_nm\x18\x03 \x01(\x03"4\n\x08Vector3D\x12\x0c\n\x04x_nm\x18\x01 \x01(\x01\x12\x0c\n\x04y_nm\x18\x02 \x01(\x01\x12\x0c\n\x04z_nm\x18\x03 \x01(\x01"`\n\x04Box2\x12-\n\x08position\x18\x01 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12)\n\x04size\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2"\x1c\n\x08Distance\x12\x10\n\x08value_nm\x18\x01 \x01(\x03"\x1e\n\x05Angle\x12\x15\n\rvalue_degrees\x18\x01 \x01(\x01"\x16\n\x05Ratio\x12\r\n\x05value\x18\x01 \x01(\x01"\x18\n\x04Time\x12\x10\n\x08value_as\x18\x01 \x01(\x03"3\n\x05Color\x12\t\n\x01r\x18\x01 \x01(\x01\x12\t\n\x01g\x18\x02 \x01(\x01\x12\t\n\x01b\x18\x03 \x01(\x01\x12\t\n\x01a\x18\x04 \x01(\x01"\x90\x01\n\x0eArcStartMidEnd\x12*\n\x05start\x18\x01 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12(\n\x03mid\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12(\n\x03end\x18\x03 \x01(\x0b2\x1b.kiapi.common.types.Vector2"{\n\x0cPolyLineNode\x12,\n\x05point\x18\x01 \x01(\x0b2\x1b.kiapi.common.types.Vector2H\x00\x121\n\x03arc\x18\x02 \x01(\x0b2".kiapi.common.types.ArcStartMidEndH\x00B\n\n\x08geometry"K\n\x08PolyLine\x12/\n\x05nodes\x18\x01 \x03(\x0b2 .kiapi.common.types.PolyLineNode\x12\x0e\n\x06closed\x18\x02 \x01(\x08"n\n\x10PolygonWithHoles\x12-\n\x07outline\x18\x01 \x01(\x0b2\x1c.kiapi.common.types.PolyLine\x12+\n\x05holes\x18\x02 \x03(\x0b2\x1c.kiapi.common.types.PolyLine"A\n\x07PolySet\x126\n\x08polygons\x18\x01 \x03(\x0b2$.kiapi.common.types.PolygonWithHoles"\xca\x03\n\x0eTextAttributes\x12\x11\n\tfont_name\x18\x01 \x01(\t\x12E\n\x14horizontal_alignment\x18\x02 \x01(\x0e2\'.kiapi.common.types.HorizontalAlignment\x12A\n\x12vertical_alignment\x18\x03 \x01(\x0e2%.kiapi.common.types.VerticalAlignment\x12(\n\x05angle\x18\x04 \x01(\x0b2\x19.kiapi.common.types.Angle\x12\x14\n\x0cline_spacing\x18\x05 \x01(\x01\x122\n\x0cstroke_width\x18\x06 \x01(\x0b2\x1c.kiapi.common.types.Distance\x12\x0e\n\x06italic\x18\x07 \x01(\x08\x12\x0c\n\x04bold\x18\x08 \x01(\x08\x12\x12\n\nunderlined\x18\t \x01(\x08\x12\x0f\n\x07visible\x18\n \x01(\x08\x12\x10\n\x08mirrored\x18\x0b \x01(\x08\x12\x11\n\tmultiline\x18\x0c \x01(\x08\x12\x14\n\x0ckeep_upright\x18\r \x01(\x08\x12)\n\x04size\x18\x0e \x01(\x0b2\x1b.kiapi.common.types.Vector2"\x8e\x01\n\x04Text\x12-\n\x08position\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x126\n\nattributes\x18\x03 \x01(\x0b2".kiapi.common.types.TextAttributes\x12\x0c\n\x04text\x18\x05 \x01(\t\x12\x11\n\thyperlink\x18\x06 \x01(\t"\xb1\x01\n\x07TextBox\x12-\n\x08top_left\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x121\n\x0cbottom_right\x18\x03 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x126\n\nattributes\x18\x04 \x01(\x0b2".kiapi.common.types.TextAttributes\x12\x0c\n\x04text\x18\x06 \x01(\t"\x9d\x01\n\x10StrokeAttributes\x12+\n\x05width\x18\x01 \x01(\x0b2\x1c.kiapi.common.types.Distance\x122\n\x05style\x18\x02 \x01(\x0e2#.kiapi.common.types.StrokeLineStyle\x12(\n\x05color\x18\x03 \x01(\x0b2\x19.kiapi.common.types.Color"y\n\x15GraphicFillAttributes\x126\n\tfill_type\x18\x01 \x01(\x0e2#.kiapi.common.types.GraphicFillType\x12(\n\x05color\x18\x02 \x01(\x0b2\x19.kiapi.common.types.Color"\x82\x01\n\x11GraphicAttributes\x124\n\x06stroke\x18\x01 \x01(\x0b2$.kiapi.common.types.StrokeAttributes\x127\n\x04fill\x18\x02 \x01(\x0b2).kiapi.common.types.GraphicFillAttributes"p\n\x18GraphicSegmentAttributes\x12*\n\x05start\x18\x01 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12(\n\x03end\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2"\xb3\x01\n\x1aGraphicRectangleAttributes\x12-\n\x08top_left\x18\x01 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x121\n\x0cbottom_right\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x123\n\rcorner_radius\x18\x03 \x01(\x0b2\x1c.kiapi.common.types.Distance"\x96\x01\n\x14GraphicArcAttributes\x12*\n\x05start\x18\x01 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12(\n\x03mid\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12(\n\x03end\x18\x03 \x01(\x0b2\x1b.kiapi.common.types.Vector2"y\n\x17GraphicCircleAttributes\x12+\n\x06center\x18\x01 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x121\n\x0cradius_point\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2"\xcd\x01\n\x17GraphicBezierAttributes\x12*\n\x05start\x18\x01 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12-\n\x08control1\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12-\n\x08control2\x18\x03 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12(\n\x03end\x18\x04 \x01(\x0b2\x1b.kiapi.common.types.Vector2"\xc2\x03\n\x0cGraphicShape\x129\n\nattributes\x18\x03 \x01(\x0b2%.kiapi.common.types.GraphicAttributes\x12?\n\x07segment\x18\x04 \x01(\x0b2,.kiapi.common.types.GraphicSegmentAttributesH\x00\x12C\n\trectangle\x18\x05 \x01(\x0b2..kiapi.common.types.GraphicRectangleAttributesH\x00\x127\n\x03arc\x18\x06 \x01(\x0b2(.kiapi.common.types.GraphicArcAttributesH\x00\x12=\n\x06circle\x18\x07 \x01(\x0b2+.kiapi.common.types.GraphicCircleAttributesH\x00\x12.\n\x07polygon\x18\x08 \x01(\x0b2\x1b.kiapi.common.types.PolySetH\x00\x12=\n\x06bezier\x18\t \x01(\x0b2+.kiapi.common.types.GraphicBezierAttributesH\x00B\n\n\x08geometry"A\n\rCompoundShape\x120\n\x06shapes\x18\x01 \x03(\x0b2 .kiapi.common.types.GraphicShape"\xf2\x01\n\x0eTitleBlockInfo\x12\r\n\x05title\x18\x01 \x01(\t\x12\x0c\n\x04date\x18\x02 \x01(\t\x12\x10\n\x08revision\x18\x03 \x01(\t\x12\x0f\n\x07company\x18\x04 \x01(\t\x12\x10\n\x08comment1\x18\x05 \x01(\t\x12\x10\n\x08comment2\x18\x06 \x01(\t\x12\x10\n\x08comment3\x18\x07 \x01(\t\x12\x10\n\x08comment4\x18\x08 \x01(\t\x12\x10\n\x08comment5\x18\t \x01(\t\x12\x10\n\x08comment6\x18\n \x01(\t\x12\x10\n\x08comment7\x18\x0b \x01(\t\x12\x10\n\x08comment8\x18\x0c \x01(\t\x12\x10\n\x08comment9\x18\r \x01(\t*9\n\rCommandStatus\x12\x0e\n\nCS_UNKNOWN\x10\x00\x12\t\n\x05CS_OK\x10\x01\x12\r\n\tCS_FAILED\x10\x02*\xc3\x01\n\tFrameType\x12\x0e\n\nFT_UNKNOWN\x10\x00\x12\x16\n\x12FT_PROJECT_MANAGER\x10\x01\x12\x17\n\x13FT_SCHEMATIC_EDITOR\x10\x02\x12\x11\n\rFT_PCB_EDITOR\x10\x03\x12\x16\n\x12FT_SPICE_SIMULATOR\x10\x04\x12\x14\n\x10FT_SYMBOL_EDITOR\x10\x05\x12\x17\n\x13FT_FOOTPRINT_EDITOR\x10\x06\x12\x1b\n\x17FT_DRAWING_SHEET_EDITOR\x10\x07*\xa6\x01\n\x0cDocumentType\x12\x13\n\x0fDOCTYPE_UNKNOWN\x10\x00\x12\x15\n\x11DOCTYPE_SCHEMATIC\x10\x01\x12\x12\n\x0eDOCTYPE_SYMBOL\x10\x02\x12\x0f\n\x0bDOCTYPE_PCB\x10\x03\x12\x15\n\x11DOCTYPE_FOOTPRINT\x10\x04\x12\x19\n\x15DOCTYPE_DRAWING_SHEET\x10\x05\x12\x13\n\x0fDOCTYPE_PROJECT\x10\x06*h\n\x11ItemRequestStatus\x12\x0f\n\x0bIRS_UNKNOWN\x10\x00\x12\n\n\x06IRS_OK\x10\x01\x12\x1a\n\x16IRS_DOCUMENT_NOT_FOUND\x10\x02\x12\x1a\n\x16IRS_FIELD_MASK_INVALID\x10\x03*=\n\x0bLockedState\x12\x0e\n\nLS_UNKNOWN\x10\x00\x12\x0f\n\x0bLS_UNLOCKED\x10\x01\x12\r\n\tLS_LOCKED\x10\x02*D\n\x0fGraphicFillType\x12\x0f\n\x0bGFT_UNKNOWN\x10\x00\x12\x10\n\x0cGFT_UNFILLED\x10\x01\x12\x0e\n\nGFT_FILLED\x10\x02*=\n\rAxisAlignment\x12\x0e\n\nAA_UNKNOWN\x10\x00\x12\r\n\tAA_X_AXIS\x10\x01\x12\r\n\tAA_Y_AXIS\x10\x02*?\n\x0cMapMergeMode\x12\x0f\n\x0bMMM_UNKNOWN\x10\x00\x12\r\n\tMMM_MERGE\x10\x01\x12\x0f\n\x0bMMM_REPLACE\x10\x02*\x8d\x02\n\x11ElectricalPinType\x12\x0f\n\x0bEPT_UNKNOWN\x10\x00\x12\r\n\tEPT_INPUT\x10\x01\x12\x0e\n\nEPT_OUTPUT\x10\x02\x12\x15\n\x11EPT_BIDIRECTIONAL\x10\x03\x12\x10\n\x0cEPT_TRISTATE\x10\x04\x12\x0f\n\x0bEPT_PASSIVE\x10\x05\x12\x0c\n\x08EPT_FREE\x10\x06\x12\x13\n\x0fEPT_UNSPECIFIED\x10\x07\x12\x13\n\x0fEPT_POWER_INPUT\x10\x08\x12\x14\n\x10EPT_POWER_OUTPUT\x10\t\x12\x16\n\x12EPT_OPEN_COLLECTOR\x10\n\x12\x14\n\x10EPT_OPEN_EMITTER\x10\x0b\x12\x12\n\x0eEPT_NO_CONNECT\x10\x0cb\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'common.types.base_types_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_COMMANDSTATUS']._serialized_start = 4616
    _globals['_COMMANDSTATUS']._serialized_end = 4673
    _globals['_FRAMETYPE']._serialized_start = 4676
    _globals['_FRAMETYPE']._serialized_end = 4871
    _globals['_DOCUMENTTYPE']._serialized_start = 4874
    _globals['_DOCUMENTTYPE']._serialized_end = 5040
    _globals['_ITEMREQUESTSTATUS']._serialized_start = 5042
    _globals['_ITEMREQUESTSTATUS']._serialized_end = 5146
    _globals['_LOCKEDSTATE']._serialized_start = 5148
    _globals['_LOCKEDSTATE']._serialized_end = 5209
    _globals['_GRAPHICFILLTYPE']._serialized_start = 5211
    _globals['_GRAPHICFILLTYPE']._serialized_end = 5279
    _globals['_AXISALIGNMENT']._serialized_start = 5281
    _globals['_AXISALIGNMENT']._serialized_end = 5342
    _globals['_MAPMERGEMODE']._serialized_start = 5344
    _globals['_MAPMERGEMODE']._serialized_end = 5407
    _globals['_ELECTRICALPINTYPE']._serialized_start = 5410
    _globals['_ELECTRICALPINTYPE']._serialized_end = 5679
    _globals['_COMMANDSTATUSRESPONSE']._serialized_start = 113
    _globals['_COMMANDSTATUSRESPONSE']._serialized_end = 187
    _globals['_KICADVERSION']._serialized_start = 189
    _globals['_KICADVERSION']._serialized_end = 270
    _globals['_KIID']._serialized_start = 272
    _globals['_KIID']._serialized_end = 293
    _globals['_LIBRARYIDENTIFIER']._serialized_start = 295
    _globals['_LIBRARYIDENTIFIER']._serialized_end = 360
    _globals['_SHEETPATH']._serialized_start = 362
    _globals['_SHEETPATH']._serialized_end = 442
    _globals['_PROJECTSPECIFIER']._serialized_start = 444
    _globals['_PROJECTSPECIFIER']._serialized_end = 490
    _globals['_DOCUMENTSPECIFIER']._serialized_start = 493
    _globals['_DOCUMENTSPECIFIER']._serialized_end = 765
    _globals['_ITEMHEADER']._serialized_start = 768
    _globals['_ITEMHEADER']._serialized_end = 930
    _globals['_VECTOR2']._serialized_start = 932
    _globals['_VECTOR2']._serialized_end = 969
    _globals['_VECTOR3']._serialized_start = 971
    _globals['_VECTOR3']._serialized_end = 1022
    _globals['_VECTOR3D']._serialized_start = 1024
    _globals['_VECTOR3D']._serialized_end = 1076
    _globals['_BOX2']._serialized_start = 1078
    _globals['_BOX2']._serialized_end = 1174
    _globals['_DISTANCE']._serialized_start = 1176
    _globals['_DISTANCE']._serialized_end = 1204
    _globals['_ANGLE']._serialized_start = 1206
    _globals['_ANGLE']._serialized_end = 1236
    _globals['_RATIO']._serialized_start = 1238
    _globals['_RATIO']._serialized_end = 1260
    _globals['_TIME']._serialized_start = 1262
    _globals['_TIME']._serialized_end = 1286
    _globals['_COLOR']._serialized_start = 1288
    _globals['_COLOR']._serialized_end = 1339
    _globals['_ARCSTARTMIDEND']._serialized_start = 1342
    _globals['_ARCSTARTMIDEND']._serialized_end = 1486
    _globals['_POLYLINENODE']._serialized_start = 1488
    _globals['_POLYLINENODE']._serialized_end = 1611
    _globals['_POLYLINE']._serialized_start = 1613
    _globals['_POLYLINE']._serialized_end = 1688
    _globals['_POLYGONWITHHOLES']._serialized_start = 1690
    _globals['_POLYGONWITHHOLES']._serialized_end = 1800
    _globals['_POLYSET']._serialized_start = 1802
    _globals['_POLYSET']._serialized_end = 1867
    _globals['_TEXTATTRIBUTES']._serialized_start = 1870
    _globals['_TEXTATTRIBUTES']._serialized_end = 2328
    _globals['_TEXT']._serialized_start = 2331
    _globals['_TEXT']._serialized_end = 2473
    _globals['_TEXTBOX']._serialized_start = 2476
    _globals['_TEXTBOX']._serialized_end = 2653
    _globals['_STROKEATTRIBUTES']._serialized_start = 2656
    _globals['_STROKEATTRIBUTES']._serialized_end = 2813
    _globals['_GRAPHICFILLATTRIBUTES']._serialized_start = 2815
    _globals['_GRAPHICFILLATTRIBUTES']._serialized_end = 2936
    _globals['_GRAPHICATTRIBUTES']._serialized_start = 2939
    _globals['_GRAPHICATTRIBUTES']._serialized_end = 3069
    _globals['_GRAPHICSEGMENTATTRIBUTES']._serialized_start = 3071
    _globals['_GRAPHICSEGMENTATTRIBUTES']._serialized_end = 3183
    _globals['_GRAPHICRECTANGLEATTRIBUTES']._serialized_start = 3186
    _globals['_GRAPHICRECTANGLEATTRIBUTES']._serialized_end = 3365
    _globals['_GRAPHICARCATTRIBUTES']._serialized_start = 3368
    _globals['_GRAPHICARCATTRIBUTES']._serialized_end = 3518
    _globals['_GRAPHICCIRCLEATTRIBUTES']._serialized_start = 3520
    _globals['_GRAPHICCIRCLEATTRIBUTES']._serialized_end = 3641
    _globals['_GRAPHICBEZIERATTRIBUTES']._serialized_start = 3644
    _globals['_GRAPHICBEZIERATTRIBUTES']._serialized_end = 3849
    _globals['_GRAPHICSHAPE']._serialized_start = 3852
    _globals['_GRAPHICSHAPE']._serialized_end = 4302
    _globals['_COMPOUNDSHAPE']._serialized_start = 4304
    _globals['_COMPOUNDSHAPE']._serialized_end = 4369
    _globals['_TITLEBLOCKINFO']._serialized_start = 4372
    _globals['_TITLEBLOCKINFO']._serialized_end = 4614