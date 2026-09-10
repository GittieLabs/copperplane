"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 6, '', 'common/types/enums.proto')
_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x18common/types/enums.proto\x12\x12kiapi.common.types*\xeb\x07\n\x0fKiCadObjectType\x12\x0f\n\x0bKOT_UNKNOWN\x10\x00\x12\x15\n\x11KOT_PCB_FOOTPRINT\x10\x01\x12\x0f\n\x0bKOT_PCB_PAD\x10\x02\x12\x11\n\rKOT_PCB_SHAPE\x10\x03\x12\x1b\n\x17KOT_PCB_REFERENCE_IMAGE\x10\x04\x12\x11\n\rKOT_PCB_FIELD\x10\x05\x12\x15\n\x11KOT_PCB_GENERATOR\x10\x06\x12\x10\n\x0cKOT_PCB_TEXT\x10\x07\x12\x13\n\x0fKOT_PCB_TEXTBOX\x10\x08\x12\x11\n\rKOT_PCB_TABLE\x10\t\x12\x15\n\x11KOT_PCB_TABLECELL\x10\n\x12\x11\n\rKOT_PCB_TRACE\x10\x0b\x12\x0f\n\x0bKOT_PCB_VIA\x10\x0c\x12\x0f\n\x0bKOT_PCB_ARC\x10\r\x12\x12\n\x0eKOT_PCB_MARKER\x10\x0e\x12\x15\n\x11KOT_PCB_DIMENSION\x10\x0f\x12\x10\n\x0cKOT_PCB_ZONE\x10\x10\x12\x11\n\rKOT_PCB_GROUP\x10\x11\x12\x12\n\x0eKOT_SCH_MARKER\x10\x12\x12\x14\n\x10KOT_SCH_JUNCTION\x10\x13\x12\x16\n\x12KOT_SCH_NO_CONNECT\x10\x14\x12\x1a\n\x16KOT_SCH_BUS_WIRE_ENTRY\x10\x15\x12\x19\n\x15KOT_SCH_BUS_BUS_ENTRY\x10\x16\x12\x10\n\x0cKOT_SCH_LINE\x10\x17\x12\x11\n\rKOT_SCH_SHAPE\x10\x18\x12\x12\n\x0eKOT_SCH_BITMAP\x10\x19\x12\x13\n\x0fKOT_SCH_TEXTBOX\x10\x1a\x12\x10\n\x0cKOT_SCH_TEXT\x10\x1b\x12\x11\n\rKOT_SCH_TABLE\x10\x1c\x12\x15\n\x11KOT_SCH_TABLECELL\x10\x1d\x12\x11\n\rKOT_SCH_LABEL\x10\x1e\x12\x18\n\x14KOT_SCH_GLOBAL_LABEL\x10\x1f\x12\x16\n\x12KOT_SCH_HIER_LABEL\x10 \x12\x1b\n\x17KOT_SCH_DIRECTIVE_LABEL\x10!\x12\x11\n\rKOT_SCH_FIELD\x10"\x12\x12\n\x0eKOT_SCH_SYMBOL\x10#\x12\x15\n\x11KOT_SCH_SHEET_PIN\x10$\x12\x11\n\rKOT_SCH_SHEET\x10%\x12\x0f\n\x0bKOT_SCH_PIN\x10&\x12\x12\n\x0eKOT_LIB_SYMBOL\x10\'\x12\x10\n\x0cKOT_WSG_LINE\x10-\x12\x10\n\x0cKOT_WSG_RECT\x10.\x12\x10\n\x0cKOT_WSG_POLY\x10/\x12\x10\n\x0cKOT_WSG_TEXT\x100\x12\x12\n\x0eKOT_WSG_BITMAP\x101\x12\x10\n\x0cKOT_WSG_PAGE\x102\x12\x11\n\rKOT_SCH_GROUP\x103\x12\x13\n\x0fKOT_PCB_BARCODE\x104*e\n\x13HorizontalAlignment\x12\x0e\n\nHA_UNKNOWN\x10\x00\x12\x0b\n\x07HA_LEFT\x10\x01\x12\r\n\tHA_CENTER\x10\x02\x12\x0c\n\x08HA_RIGHT\x10\x03\x12\x14\n\x10HA_INDETERMINATE\x10\x04*c\n\x11VerticalAlignment\x12\x0e\n\nVA_UNKNOWN\x10\x00\x12\n\n\x06VA_TOP\x10\x01\x12\r\n\tVA_CENTER\x10\x02\x12\r\n\tVA_BOTTOM\x10\x03\x12\x14\n\x10VA_INDETERMINATE\x10\x04*\x82\x01\n\x0fStrokeLineStyle\x12\x0f\n\x0bSLS_UNKNOWN\x10\x00\x12\x0f\n\x0bSLS_DEFAULT\x10\x01\x12\r\n\tSLS_SOLID\x10\x02\x12\x0c\n\x08SLS_DASH\x10\x03\x12\x0b\n\x07SLS_DOT\x10\x04\x12\x0f\n\x0bSLS_DASHDOT\x10\x05\x12\x12\n\x0eSLS_DASHDOTDOT\x10\x06b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'common.types.enums_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_KICADOBJECTTYPE']._serialized_start = 49
    _globals['_KICADOBJECTTYPE']._serialized_end = 1052
    _globals['_HORIZONTALALIGNMENT']._serialized_start = 1054
    _globals['_HORIZONTALALIGNMENT']._serialized_end = 1155
    _globals['_VERTICALALIGNMENT']._serialized_start = 1157
    _globals['_VERTICALALIGNMENT']._serialized_end = 1256
    _globals['_STROKELINESTYLE']._serialized_start = 1259
    _globals['_STROKELINESTYLE']._serialized_end = 1389