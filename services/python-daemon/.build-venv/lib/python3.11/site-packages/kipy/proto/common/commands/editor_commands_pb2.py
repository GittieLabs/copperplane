"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 6, '', 'common/commands/editor_commands.proto')
_sym_db = _symbol_database.Default()
from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2
from ...common.types import base_types_pb2 as common_dot_types_dot_base__types__pb2
from ...common.types import enums_pb2 as common_dot_types_dot_enums__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n%common/commands/editor_commands.proto\x12\x15kiapi.common.commands\x1a\x19google/protobuf/any.proto\x1a\x1dcommon/types/base_types.proto\x1a\x18common/types/enums.proto"=\n\rRefreshEditor\x12,\n\x05frame\x18\x01 \x01(\x0e2\x1d.kiapi.common.types.FrameType"B\n\x10GetOpenDocuments\x12.\n\x04type\x18\x01 \x01(\x0e2 .kiapi.common.types.DocumentType"T\n\x18GetOpenDocumentsResponse\x128\n\tdocuments\x18\x01 \x03(\x0b2%.kiapi.common.types.DocumentSpecifier"G\n\x0cSaveDocument\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier"9\n\x0bSaveOptions\x12\x11\n\toverwrite\x18\x01 \x01(\x08\x12\x17\n\x0finclude_project\x18\x02 \x01(\x08"\x90\x01\n\x12SaveCopyOfDocument\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier\x12\x0c\n\x04path\x18\x02 \x01(\t\x123\n\x07options\x18\x03 \x01(\x0b2".kiapi.common.commands.SaveOptions"I\n\x0eRevertDocument\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier"\x1b\n\tRunAction\x12\x0e\n\x06action\x18\x01 \x01(\t"K\n\x11RunActionResponse\x126\n\x06status\x18\x01 \x01(\x0e2&.kiapi.common.commands.RunActionStatus"\r\n\x0bBeginCommit";\n\x13BeginCommitResponse\x12$\n\x02id\x18\x01 \x01(\x0b2\x18.kiapi.common.types.KIID"w\n\tEndCommit\x12$\n\x02id\x18\x01 \x01(\x0b2\x18.kiapi.common.types.KIID\x123\n\x06action\x18\x02 \x01(\x0e2#.kiapi.common.commands.CommitAction\x12\x0f\n\x07message\x18\x03 \x01(\t"\x13\n\x11EndCommitResponse"\x8f\x01\n\x0bCreateItems\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x12#\n\x05items\x18\x02 \x03(\x0b2\x14.google.protobuf.Any\x12+\n\tcontainer\x18\x03 \x01(\x0b2\x18.kiapi.common.types.KIID"X\n\nItemStatus\x123\n\x04code\x18\x01 \x01(\x0e2%.kiapi.common.commands.ItemStatusCode\x12\x15\n\rerror_message\x18\x02 \x01(\t"k\n\x12ItemCreationResult\x121\n\x06status\x18\x01 \x01(\x0b2!.kiapi.common.commands.ItemStatus\x12"\n\x04item\x18\x02 \x01(\x0b2\x14.google.protobuf.Any"\xbe\x01\n\x13CreateItemsResponse\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x125\n\x06status\x18\x02 \x01(\x0e2%.kiapi.common.types.ItemRequestStatus\x12@\n\rcreated_items\x18\x03 \x03(\x0b2).kiapi.common.commands.ItemCreationResult"n\n\x08GetItems\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x122\n\x05types\x18\x02 \x03(\x0e2#.kiapi.common.types.KiCadObjectType"g\n\x0cGetItemsById\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x12\'\n\x05items\x18\x02 \x03(\x0b2\x18.kiapi.common.types.KIID"\x9e\x01\n\x10GetItemsResponse\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x125\n\x06status\x18\x02 \x01(\x0e2%.kiapi.common.types.ItemRequestStatus\x12#\n\x05items\x18\x03 \x03(\x0b2\x14.google.protobuf.Any"b\n\x0bUpdateItems\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x12#\n\x05items\x18\x02 \x03(\x0b2\x14.google.protobuf.Any"i\n\x10ItemUpdateResult\x121\n\x06status\x18\x01 \x01(\x0b2!.kiapi.common.commands.ItemStatus\x12"\n\x04item\x18\x02 \x01(\x0b2\x14.google.protobuf.Any"\xbc\x01\n\x13UpdateItemsResponse\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x125\n\x06status\x18\x02 \x01(\x0e2%.kiapi.common.types.ItemRequestStatus\x12>\n\rupdated_items\x18\x03 \x03(\x0b2\'.kiapi.common.commands.ItemUpdateResult"i\n\x0bDeleteItems\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x12*\n\x08item_ids\x18\x02 \x03(\x0b2\x18.kiapi.common.types.KIID"u\n\x12ItemDeletionResult\x12$\n\x02id\x18\x01 \x01(\x0b2\x18.kiapi.common.types.KIID\x129\n\x06status\x18\x02 \x01(\x0e2).kiapi.common.commands.ItemDeletionStatus"\xbe\x01\n\x13DeleteItemsResponse\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x125\n\x06status\x18\x02 \x01(\x0e2%.kiapi.common.types.ItemRequestStatus\x12@\n\rdeleted_items\x18\x03 \x03(\x0b2).kiapi.common.commands.ItemDeletionResult"\x9f\x01\n\x0eGetBoundingBox\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x12\'\n\x05items\x18\x02 \x03(\x0b2\x18.kiapi.common.types.KIID\x124\n\x04mode\x18\x03 \x01(\x0e2&.kiapi.common.commands.BoundingBoxMode"j\n\x16GetBoundingBoxResponse\x12\'\n\x05items\x18\x01 \x03(\x0b2\x18.kiapi.common.types.KIID\x12\'\n\x05boxes\x18\x02 \x03(\x0b2\x18.kiapi.common.types.Box2"r\n\x0cGetSelection\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x122\n\x05types\x18\x02 \x03(\x0e2#.kiapi.common.types.KiCadObjectType"8\n\x11SelectionResponse\x12#\n\x05items\x18\x01 \x03(\x0b2\x14.google.protobuf.Any"i\n\x0eAddToSelection\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x12\'\n\x05items\x18\x02 \x03(\x0b2\x18.kiapi.common.types.KIID"n\n\x13RemoveFromSelection\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x12\'\n\x05items\x18\x02 \x03(\x0b2\x18.kiapi.common.types.KIID"@\n\x0eClearSelection\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader"\xa1\x01\n\x07HitTest\x12.\n\x06header\x18\x01 \x01(\x0b2\x1e.kiapi.common.types.ItemHeader\x12$\n\x02id\x18\x02 \x01(\x0b2\x18.kiapi.common.types.KIID\x12-\n\x08position\x18\x03 \x01(\x0b2\x1b.kiapi.common.types.Vector2\x12\x11\n\ttolerance\x18\x04 \x01(\x05"G\n\x0fHitTestResponse\x124\n\x06result\x18\x01 \x01(\x0e2$.kiapi.common.commands.HitTestResult"L\n\x11GetTitleBlockInfo\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier"\x85\x01\n\x11SetTitleBlockInfo\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier\x127\n\x0btitle_block\x18\x02 \x01(\x0b2".kiapi.common.types.TitleBlockInfo"O\n\x14SaveDocumentToString\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier"b\n\x15SavedDocumentResponse\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier\x12\x10\n\x08contents\x18\x02 \x01(\t"\x17\n\x15SaveSelectionToString"Q\n\x16SavedSelectionResponse\x12%\n\x03ids\x18\x01 \x03(\x0b2\x18.kiapi.common.types.KIID\x12\x10\n\x08contents\x18\x02 \x01(\t"j\n\x1dParseAndCreateItemsFromString\x127\n\x08document\x18\x01 \x01(\x0b2%.kiapi.common.types.DocumentSpecifier\x12\x10\n\x08contents\x18\x02 \x01(\t*W\n\x0fRunActionStatus\x12\x0f\n\x0bRAS_UNKNOWN\x10\x00\x12\n\n\x06RAS_OK\x10\x01\x12\x0f\n\x0bRAS_INVALID\x10\x02\x12\x16\n\x12RAS_FRAME_NOT_OPEN\x10\x03*=\n\x0cCommitAction\x12\x0f\n\x0bCMA_UNKNOWN\x10\x00\x12\x0e\n\nCMA_COMMIT\x10\x01\x12\x0c\n\x08CMA_DROP\x10\x02*\x93\x01\n\x0eItemStatusCode\x12\x0f\n\x0bISC_UNKNOWN\x10\x00\x12\n\n\x06ISC_OK\x10\x01\x12\x14\n\x10ISC_INVALID_TYPE\x10\x02\x12\x10\n\x0cISC_EXISTING\x10\x03\x12\x13\n\x0fISC_NONEXISTENT\x10\x04\x12\x11\n\rISC_IMMUTABLE\x10\x05\x12\x14\n\x10ISC_INVALID_DATA\x10\x07*Y\n\x12ItemDeletionStatus\x12\x0f\n\x0bIDS_UNKNOWN\x10\x00\x12\n\n\x06IDS_OK\x10\x01\x12\x13\n\x0fIDS_NONEXISTENT\x10\x02\x12\x11\n\rIDS_IMMUTABLE\x10\x03*R\n\x0fBoundingBoxMode\x12\x0f\n\x0bBBM_UNKNOWN\x10\x00\x12\x11\n\rBBM_ITEM_ONLY\x10\x01\x12\x1b\n\x17BBM_ITEM_AND_CHILD_TEXT\x10\x02*=\n\rHitTestResult\x12\x0f\n\x0bHTR_UNKNOWN\x10\x00\x12\x0e\n\nHTR_NO_HIT\x10\x01\x12\x0b\n\x07HTR_HIT\x10\x02b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'common.commands.editor_commands_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_RUNACTIONSTATUS']._serialized_start = 4353
    _globals['_RUNACTIONSTATUS']._serialized_end = 4440
    _globals['_COMMITACTION']._serialized_start = 4442
    _globals['_COMMITACTION']._serialized_end = 4503
    _globals['_ITEMSTATUSCODE']._serialized_start = 4506
    _globals['_ITEMSTATUSCODE']._serialized_end = 4653
    _globals['_ITEMDELETIONSTATUS']._serialized_start = 4655
    _globals['_ITEMDELETIONSTATUS']._serialized_end = 4744
    _globals['_BOUNDINGBOXMODE']._serialized_start = 4746
    _globals['_BOUNDINGBOXMODE']._serialized_end = 4828
    _globals['_HITTESTRESULT']._serialized_start = 4830
    _globals['_HITTESTRESULT']._serialized_end = 4891
    _globals['_REFRESHEDITOR']._serialized_start = 148
    _globals['_REFRESHEDITOR']._serialized_end = 209
    _globals['_GETOPENDOCUMENTS']._serialized_start = 211
    _globals['_GETOPENDOCUMENTS']._serialized_end = 277
    _globals['_GETOPENDOCUMENTSRESPONSE']._serialized_start = 279
    _globals['_GETOPENDOCUMENTSRESPONSE']._serialized_end = 363
    _globals['_SAVEDOCUMENT']._serialized_start = 365
    _globals['_SAVEDOCUMENT']._serialized_end = 436
    _globals['_SAVEOPTIONS']._serialized_start = 438
    _globals['_SAVEOPTIONS']._serialized_end = 495
    _globals['_SAVECOPYOFDOCUMENT']._serialized_start = 498
    _globals['_SAVECOPYOFDOCUMENT']._serialized_end = 642
    _globals['_REVERTDOCUMENT']._serialized_start = 644
    _globals['_REVERTDOCUMENT']._serialized_end = 717
    _globals['_RUNACTION']._serialized_start = 719
    _globals['_RUNACTION']._serialized_end = 746
    _globals['_RUNACTIONRESPONSE']._serialized_start = 748
    _globals['_RUNACTIONRESPONSE']._serialized_end = 823
    _globals['_BEGINCOMMIT']._serialized_start = 825
    _globals['_BEGINCOMMIT']._serialized_end = 838
    _globals['_BEGINCOMMITRESPONSE']._serialized_start = 840
    _globals['_BEGINCOMMITRESPONSE']._serialized_end = 899
    _globals['_ENDCOMMIT']._serialized_start = 901
    _globals['_ENDCOMMIT']._serialized_end = 1020
    _globals['_ENDCOMMITRESPONSE']._serialized_start = 1022
    _globals['_ENDCOMMITRESPONSE']._serialized_end = 1041
    _globals['_CREATEITEMS']._serialized_start = 1044
    _globals['_CREATEITEMS']._serialized_end = 1187
    _globals['_ITEMSTATUS']._serialized_start = 1189
    _globals['_ITEMSTATUS']._serialized_end = 1277
    _globals['_ITEMCREATIONRESULT']._serialized_start = 1279
    _globals['_ITEMCREATIONRESULT']._serialized_end = 1386
    _globals['_CREATEITEMSRESPONSE']._serialized_start = 1389
    _globals['_CREATEITEMSRESPONSE']._serialized_end = 1579
    _globals['_GETITEMS']._serialized_start = 1581
    _globals['_GETITEMS']._serialized_end = 1691
    _globals['_GETITEMSBYID']._serialized_start = 1693
    _globals['_GETITEMSBYID']._serialized_end = 1796
    _globals['_GETITEMSRESPONSE']._serialized_start = 1799
    _globals['_GETITEMSRESPONSE']._serialized_end = 1957
    _globals['_UPDATEITEMS']._serialized_start = 1959
    _globals['_UPDATEITEMS']._serialized_end = 2057
    _globals['_ITEMUPDATERESULT']._serialized_start = 2059
    _globals['_ITEMUPDATERESULT']._serialized_end = 2164
    _globals['_UPDATEITEMSRESPONSE']._serialized_start = 2167
    _globals['_UPDATEITEMSRESPONSE']._serialized_end = 2355
    _globals['_DELETEITEMS']._serialized_start = 2357
    _globals['_DELETEITEMS']._serialized_end = 2462
    _globals['_ITEMDELETIONRESULT']._serialized_start = 2464
    _globals['_ITEMDELETIONRESULT']._serialized_end = 2581
    _globals['_DELETEITEMSRESPONSE']._serialized_start = 2584
    _globals['_DELETEITEMSRESPONSE']._serialized_end = 2774
    _globals['_GETBOUNDINGBOX']._serialized_start = 2777
    _globals['_GETBOUNDINGBOX']._serialized_end = 2936
    _globals['_GETBOUNDINGBOXRESPONSE']._serialized_start = 2938
    _globals['_GETBOUNDINGBOXRESPONSE']._serialized_end = 3044
    _globals['_GETSELECTION']._serialized_start = 3046
    _globals['_GETSELECTION']._serialized_end = 3160
    _globals['_SELECTIONRESPONSE']._serialized_start = 3162
    _globals['_SELECTIONRESPONSE']._serialized_end = 3218
    _globals['_ADDTOSELECTION']._serialized_start = 3220
    _globals['_ADDTOSELECTION']._serialized_end = 3325
    _globals['_REMOVEFROMSELECTION']._serialized_start = 3327
    _globals['_REMOVEFROMSELECTION']._serialized_end = 3437
    _globals['_CLEARSELECTION']._serialized_start = 3439
    _globals['_CLEARSELECTION']._serialized_end = 3503
    _globals['_HITTEST']._serialized_start = 3506
    _globals['_HITTEST']._serialized_end = 3667
    _globals['_HITTESTRESPONSE']._serialized_start = 3669
    _globals['_HITTESTRESPONSE']._serialized_end = 3740
    _globals['_GETTITLEBLOCKINFO']._serialized_start = 3742
    _globals['_GETTITLEBLOCKINFO']._serialized_end = 3818
    _globals['_SETTITLEBLOCKINFO']._serialized_start = 3821
    _globals['_SETTITLEBLOCKINFO']._serialized_end = 3954
    _globals['_SAVEDOCUMENTTOSTRING']._serialized_start = 3956
    _globals['_SAVEDOCUMENTTOSTRING']._serialized_end = 4035
    _globals['_SAVEDDOCUMENTRESPONSE']._serialized_start = 4037
    _globals['_SAVEDDOCUMENTRESPONSE']._serialized_end = 4135
    _globals['_SAVESELECTIONTOSTRING']._serialized_start = 4137
    _globals['_SAVESELECTIONTOSTRING']._serialized_end = 4160
    _globals['_SAVEDSELECTIONRESPONSE']._serialized_start = 4162
    _globals['_SAVEDSELECTIONRESPONSE']._serialized_end = 4243
    _globals['_PARSEANDCREATEITEMSFROMSTRING']._serialized_start = 4245
    _globals['_PARSEANDCREATEITEMSFROMSTRING']._serialized_end = 4351