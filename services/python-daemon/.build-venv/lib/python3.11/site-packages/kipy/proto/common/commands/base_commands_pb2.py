"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 6, '', 'common/commands/base_commands.proto')
_sym_db = _symbol_database.Default()
from ...common.types import base_types_pb2 as common_dot_types_dot_base__types__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n#common/commands/base_commands.proto\x12\x15kiapi.common.commands\x1a\x1dcommon/types/base_types.proto"\x0c\n\nGetVersion"G\n\x12GetVersionResponse\x121\n\x07version\x18\x01 \x01(\x0b2 .kiapi.common.types.KiCadVersion"\x06\n\x04Ping")\n\x12GetKiCadBinaryPath\x12\x13\n\x0bbinary_name\x18\x01 \x01(\t"\x1c\n\x0cPathResponse\x12\x0c\n\x04path\x18\x01 \x01(\t"8\n\x0eGetTextExtents\x12&\n\x04text\x18\x01 \x01(\x0b2\x18.kiapi.common.types.Text"r\n\rTextOrTextBox\x12(\n\x04text\x18\x01 \x01(\x0b2\x18.kiapi.common.types.TextH\x00\x12.\n\x07textbox\x18\x02 \x01(\x0b2\x1b.kiapi.common.types.TextBoxH\x00B\x07\n\x05inner"E\n\x0fGetTextAsShapes\x122\n\x04text\x18\x01 \x03(\x0b2$.kiapi.common.commands.TextOrTextBox"w\n\x0eTextWithShapes\x122\n\x04text\x18\x01 \x01(\x0b2$.kiapi.common.commands.TextOrTextBox\x121\n\x06shapes\x18\x02 \x01(\x0b2!.kiapi.common.types.CompoundShape"Z\n\x17GetTextAsShapesResponse\x12?\n\x10text_with_shapes\x18\x01 \x03(\x0b2%.kiapi.common.commands.TextWithShapes"+\n\x15GetPluginSettingsPath\x12\x12\n\nidentifier\x18\x01 \x01(\t""\n\x0eStringResponse\x12\x10\n\x08response\x18\x01 \x01(\tb\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'common.commands.base_commands_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_GETVERSION']._serialized_start = 93
    _globals['_GETVERSION']._serialized_end = 105
    _globals['_GETVERSIONRESPONSE']._serialized_start = 107
    _globals['_GETVERSIONRESPONSE']._serialized_end = 178
    _globals['_PING']._serialized_start = 180
    _globals['_PING']._serialized_end = 186
    _globals['_GETKICADBINARYPATH']._serialized_start = 188
    _globals['_GETKICADBINARYPATH']._serialized_end = 229
    _globals['_PATHRESPONSE']._serialized_start = 231
    _globals['_PATHRESPONSE']._serialized_end = 259
    _globals['_GETTEXTEXTENTS']._serialized_start = 261
    _globals['_GETTEXTEXTENTS']._serialized_end = 317
    _globals['_TEXTORTEXTBOX']._serialized_start = 319
    _globals['_TEXTORTEXTBOX']._serialized_end = 433
    _globals['_GETTEXTASSHAPES']._serialized_start = 435
    _globals['_GETTEXTASSHAPES']._serialized_end = 504
    _globals['_TEXTWITHSHAPES']._serialized_start = 506
    _globals['_TEXTWITHSHAPES']._serialized_end = 625
    _globals['_GETTEXTASSHAPESRESPONSE']._serialized_start = 627
    _globals['_GETTEXTASSHAPESRESPONSE']._serialized_end = 717
    _globals['_GETPLUGINSETTINGSPATH']._serialized_start = 719
    _globals['_GETPLUGINSETTINGSPATH']._serialized_end = 762
    _globals['_STRINGRESPONSE']._serialized_start = 764
    _globals['_STRINGRESPONSE']._serialized_end = 798