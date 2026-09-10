"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 1, '', 'common/types/generators.proto')
_sym_db = _symbol_database.Default()
from google.protobuf import field_mask_pb2 as google_dot_protobuf_dot_field__mask__pb2
from ...common.types import enums_pb2 as common_dot_types_dot_enums__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1dcommon/types/generators.proto\x12\x12kiapi.common.types\x1a google/protobuf/field_mask.proto\x1a\x18common/types/enums.proto"\x99\x02\n\x12GeneratorParameter\x12\x12\n\nidentifier\x18\x01 \x01(\t\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x13\n\x0bdescription\x18\x03 \x01(\t\x12@\n\x08category\x18\x04 \x01(\x0e2..kiapi.common.types.GeneratorParameterCategory\x12<\n\x04type\x18\x05 \x01(\x0e2..kiapi.common.types.GeneratorParameterDataType\x12\x13\n\tint_value\x18\x06 \x01(\x05H\x00\x12\x16\n\x0cdouble_value\x18\x07 \x01(\x01H\x00\x12\x16\n\x0cstring_value\x18\x08 \x01(\tH\x00B\x07\n\x05value"\x80\x01\n\rGeneratorInfo\x123\n\x04meta\x18\x01 \x01(\x0b2%.kiapi.common.types.GeneratorMetaInfo\x12:\n\nparameters\x18\x02 \x03(\x0b2&.kiapi.common.types.GeneratorParameter"\x8d\x01\n\x11GeneratorMetaInfo\x12\x12\n\nidentifier\x18\x01 \x01(\t\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x13\n\x0bdescription\x18\x03 \x01(\t\x12A\n\x0ftypes_generated\x18\x04 \x03(\x0e2(.kiapi.common.types.GeneratedContentType*\xb2\x01\n\x1aGeneratorParameterDataType\x12\x10\n\x0cGPDT_UNKNOWN\x10\x00\x12\x11\n\rGPDT_DISTANCE\x10\x01\x12\r\n\tGPDT_AREA\x10\x02\x12\x0f\n\x0bGPDT_VOLUME\x10\x03\x12\r\n\tGPDT_TIME\x10\x04\x12\x0e\n\nGPDT_ANGLE\x10\x05\x12\x0f\n\x0bGPDT_STRING\x10\x06\x12\x10\n\x0cGPDT_INTEGER\x10\x07\x12\r\n\tGPDT_REAL\x10\x08*~\n\x1aGeneratorParameterCategory\x12\x0f\n\x0bGPC_UNKNOWN\x10\x00\x12\x0f\n\x0bGPC_PACKAGE\x10\x01\x12\x0c\n\x08GPC_PADS\x10\x02\x12\x0f\n\x0bGPC_3DMODEL\x10\x03\x12\x10\n\x0cGPC_METADATA\x10\x04\x12\r\n\tGPC_RULES\x10\x05*J\n\x14GeneratedContentType\x12\x0f\n\x0bGCT_UNKNOWN\x10\x00\x12\x0e\n\nGCT_SYMBOL\x10\x01\x12\x11\n\rGCT_FOOTPRINT\x10\x02b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'common.types.generators_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_GENERATORPARAMETERDATATYPE']._serialized_start = 673
    _globals['_GENERATORPARAMETERDATATYPE']._serialized_end = 851
    _globals['_GENERATORPARAMETERCATEGORY']._serialized_start = 853
    _globals['_GENERATORPARAMETERCATEGORY']._serialized_end = 979
    _globals['_GENERATEDCONTENTTYPE']._serialized_start = 981
    _globals['_GENERATEDCONTENTTYPE']._serialized_end = 1055
    _globals['_GENERATORPARAMETER']._serialized_start = 114
    _globals['_GENERATORPARAMETER']._serialized_end = 395
    _globals['_GENERATORINFO']._serialized_start = 398
    _globals['_GENERATORINFO']._serialized_end = 526
    _globals['_GENERATORMETAINFO']._serialized_start = 529
    _globals['_GENERATORMETAINFO']._serialized_end = 670