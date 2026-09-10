"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 6, '', 'schematic/schematic_types.proto')
_sym_db = _symbol_database.Default()
from ..common.types import base_types_pb2 as common_dot_types_dot_base__types__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1fschematic/schematic_types.proto\x12\x15kiapi.schematic.types\x1a\x1dcommon/types/base_types.proto"\xb8\x01\n\x04Line\x12$\n\x02id\x18\x01 \x01(\x0b2\x18.kiapi.common.types.KIID\x12*\n\x05start\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12(\n\x03end\x18\x03 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x124\n\x05layer\x18\x04 \x01(\x0e2%.kiapi.schematic.types.SchematicLayer".\n\x04Text\x12&\n\x04text\x18\x01 \x01(\x0b2\x18.kiapi.common.types.Text"\x8c\x01\n\nLocalLabel\x12$\n\x02id\x18\x01 \x01(\x0b2\x18.kiapi.common.types.KIID\x12-\n\x08position\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12)\n\x04text\x18\x03 \x01(\x0b2\x1b.kiapi.schematic.types.Text"\x8d\x01\n\x0bGlobalLabel\x12$\n\x02id\x18\x01 \x01(\x0b2\x18.kiapi.common.types.KIID\x12-\n\x08position\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12)\n\x04text\x18\x03 \x01(\x0b2\x1b.kiapi.schematic.types.Text"\x93\x01\n\x11HierarchicalLabel\x12$\n\x02id\x18\x01 \x01(\x0b2\x18.kiapi.common.types.KIID\x12-\n\x08position\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12)\n\x04text\x18\x03 \x01(\x0b2\x1b.kiapi.schematic.types.Text"\x90\x01\n\x0eDirectiveLabel\x12$\n\x02id\x18\x01 \x01(\x0b2\x18.kiapi.common.types.KIID\x12-\n\x08position\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12)\n\x04text\x18\x03 \x01(\x0b2\x1b.kiapi.schematic.types.Text* \n\x0eSchematicLayer\x12\x0e\n\nSL_UNKNOWN\x10\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'schematic.schematic_types_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_SCHEMATICLAYER']._serialized_start = 908
    _globals['_SCHEMATICLAYER']._serialized_end = 940
    _globals['_LINE']._serialized_start = 90
    _globals['_LINE']._serialized_end = 274
    _globals['_TEXT']._serialized_start = 276
    _globals['_TEXT']._serialized_end = 322
    _globals['_LOCALLABEL']._serialized_start = 325
    _globals['_LOCALLABEL']._serialized_end = 465
    _globals['_GLOBALLABEL']._serialized_start = 468
    _globals['_GLOBALLABEL']._serialized_end = 609
    _globals['_HIERARCHICALLABEL']._serialized_start = 612
    _globals['_HIERARCHICALLABEL']._serialized_end = 759
    _globals['_DIRECTIVELABEL']._serialized_start = 762
    _globals['_DIRECTIVELABEL']._serialized_end = 906