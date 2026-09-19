
// All commented are old offsets
// ProcessBase = reinterpret_cast<std::uintptr_t>(GetModuleHandleA(nullptr));

#define REBASE(x) (*(unsigned __int64*)((unsigned __int64)(NtCurrentTeb()->ProcessEnvironmentBlock) + 0x10) + (unsigned __int64)(x))

#define _DOFFSET(x) x
#define ARXAN_LOBBY_JMP REBASE(0x27C2270)
#define ARXAN_LOBBY_JMPTO REBASE(0x1B385BED)
#define ARXAN_LOAD_JMP REBASE(0x134D5A0)
#define ARXAN_LOAD_JMPTO REBASE(0x1D3E0B71)
#define ARXAN_SPOT4_JMP REBASE(0x22F4E60)
#define ARXAN_SPOT4_JMPTO REBASE(0x1DB375E7)
#define INT3_BO3 REBASE(0x1173)
#define INT3_2_BO3 REBASE(0x1059)
#define END_TXT_FUNCS REBASE(0x2F7C4B0)
#define BEGIN_TXT_FUNCS REBASE(0x1060)
#define ROP_RETN REBASE(0x1048)
#define ARXAN_BEGIN REBASE(0x1AAEA000)
#define ARXAN_END REBASE(0x1FAB7000)
#define ASSETPOOL_BEGIN REBASE(0x94073F0)
#define OFF_ScrVarGlob REBASE(0x5124500)
#define GSCR_FASTEXIT REBASE(0x2BDA9C3)
#define CL_DrawScreenOffset REBASE(0x13CFC10)
#define EMBLEM_ID_PTR REBASE(0x343E250)
#define BO3_HWND REBASE(0x17DF74A0)
#define s_playerData_ptr REBASE(0x3390190)
#define PTR_LobbyVMJoinEvent REBASE(0x1EE35E0)
#define PTR_DDL_MoveToName REBASE(0x24A99B0)
#define PTR_DDL_MoveToIndex REBASE(0x24A99A0)
#define PTR_DDL_GetInt REBASE(0x24A99A0)
#define PTR_DDL_SetCombatRecordID REBASE(0x1E1E870)
#define PTR_Cbuf_AddText REBASE(0x20DFF50)
#define PTR_Dvar_SetFromStringByName REBASE(0x226B0A0)
#define PTR_LobbyVM REBASE(0x157588D0) // Left off here
#define PTR_CL_DispatchConnectionless REBASE(0x134CDCD)
#define PTR_MigrationVTable REBASE(0x2F3AE90)
#define SCRVM_Error REBASE(0x12EA4E0)
#define OFF_SCRVM_RuntimeError REBASE(0x12EA450)
#define SCRVM_FS REBASE(0x513DD30)
#define LuaCrash1 REBASE(0x1C9F121)
#define LuaCrash1Rip REBASE(0x1C9F2CE)
#define LuaCrash2 REBASE(0x221CEC3)
#define LuaCrash3 REBASE(0x221C726)
#define SCR_VmErrorString REBASE(0x52660F0)
#define SCR_VMContext REBASE(0x5124850)
#define INSTANT_DISPATCH REBASE(0x143A681) // Fix dispatch 
#define OFF_IsProfileBuild REBASE(0x3258D70)
#define OFF_ScrVm_GetInt REBASE(0x12EB810)
#define OFF_ScrVm_GetString REBASE(0x12EBAC0)
#define OFF_ScrVm_GetFunc REBASE(0x12EB750)
#define OFF_ScrVm_Opcodes REBASE(0x3267350)
#define OFF_ScrVm_Opcodes2 REBASE(0x3287350)
#define OFF_Scr_GetFunction REBASE(0x1AEB450)
#define OFF_Scr_GetMethod REBASE(0x1AEB5E0)
#define OFF_DB_FindXAssetHeader REBASE(0x1420EF0)
#define DB_FindXAssetHeader(type, name, errorIfMissing, waitTime) ((__int64(__fastcall*)(int, const char*, int, int))OFF_DB_FindXAssetHeader)(type, name, errorIfMissing, waitTime)
#define OFF_s_runningUILevel REBASE(0x1686E99E)
#define OFF_Scr_GscObjLink REBASE(0x12CC320)
#define OFF_ScrVar_AllocVariableInternal REBASE(0x12D9A80)
#define PTR_Name1 REBASE(0x113A4970)
#define PTR_Name2 REBASE(0x113A48F0)
#define PTR_Lua_CoD_GetLuaState REBASE(0x1F05920)
#define PTR_LobbyMsgRW_PackageInt REBASE(0x1EEA3E0)
#define PTR_LobbyMsgRW_PackageUChar REBASE(0x1EEA450)
#define PTR_LobbyMsgRW_PackageString REBASE(0x1EEA420)
#define PTR_LobbyMsgRW_PackageXuid REBASE(0x1EEA4D0)
#define PTR_LobbyMsgRW_PackageBool REBASE(0x1EEA2E0)
#define PTR_LobbyMsgRW_PackageUInt REBASE(0x1EEA490)
#define PTR_LobbyMsgRW_PackageShort REBASE(0x1EEA400)
#define PTR_LobbyMsgRW_PackageUInt64 REBASE(0x1EEA470)
#define PTR_LobbyMsgRW_PackageArrayStart REBASE(0x1EEA260)
#define PTR_LobbyMsgRW_PackageElement REBASE(0x1EEA320)
#define PTR_LobbyMsgRW_PackageGlob REBASE(0x1EEA3B0)
#define PTR_MsgMutableClientInfo_Package REBASE(0x1EC8400)
#define PTR_lobbymsgprints REBASE(0x156CE8D0)
#define PTR_saveLobbyMsgExceptAddy REBASE(0x1EEBF74)
#define PTR_UpdatePreloadIdleFN REBASE(0x32A75A8)
#define PTR_I_stricmp REBASE(0x227CB20)
#define PTR_LobbyMsgRW_PackageChar REBASE(0x1EEA300)
#define PTR_LobbyMsgRW_PackageFloat REBASE(0x1EEA390)
//#define PTR_MsgMutableClientInfo_Package REBASE(0x1ED47D0)
#define PTR_dwInstantHandleLobbyMessage REBASE(0x143A7A0)
#define PTR_ProbeLobbyInfo REBASE(0x1EDA510)
#define PTR_NET_OutOfBandPrint REBASE(0x211B310)
#define PTR_dwCommonAddrToNetadr REBASE(0x143C380)
#define PTR_dwRegisterSecIDAndKey REBASE(0x143E140)
#define PTR_LobbyMsgTansport_SendOutOfBand REBASE(0x1EEC360)
#define PTR_LobbyMsgRW_PrepWriteMsg REBASE(0x1EEA560)
#define PTR_LobbyMsgRW_PackageUShort REBASE(0x1EEA4B0)
#define PTR_sPlayerData s_playerData_ptr
#define PTR_MSG_Init REBASE(0x20FCB80)
#define PTR_MSG_WriteString REBASE(0x20FFE20)
#define PTR_MSG_WriteShort REBASE(0x211A2D0)
#define PTR_MSG_WriteByte REBASE(0x20FF3C0)
#define PTR_MSG_WriteData REBASE(0x20FF3E0)
#define PTR_Com_ControllerIndex_GetLocalClientNum REBASE(0x20E3700)
#define PTR_Com_LocalClient_GetNetworkID REBASE(0x20E3890)
#define PTR_NET_OutOfBandData REBASE(0x211B200)
#define PTR_LobbyMsgTransport_SendToAdr REBASE(0x1EEC740)
#define PTR_MSG_ReadData REBASE(0x20FD0B0)
#define PTR_LobbyMsgRW_PrepReadData REBASE(0x1EEA150)
#define PTR_MSG_InfoResponse REBASE(0x1ED5B40)
//#define PTR_I_stricmp REBASE(0x22E9530)
#define PTR_dwInstantSendMessage REBASE(0x143A830)
#define PTR_LobbySession_GetControllingLobbySession REBASE(0x1EBFDA0)
#define PTR_LobbySession_GetSession REBASE(0x1EC1650)
#define PTR_SL_LookupCanonicalString REBASE(0x12CBBB0)
#define PTR_ScrStr_ConvertToString REBASE(0x12D7180)
#define PTR_LobbySession_GetClientByClientNum REBASE(0x1EF3FB0)
#define PTR_LobbySession_GetClientNetAdrByIndex REBASE(0x1EBFCC0)
#define PTR_LobbyJoin_Reserve REBASE(0x1EDBA00)
#define PTR_CL_GetConfigString REBASE(0x1321130)
#define PTR_LiveFriends_IsFriendByXUID REBASE(0x1DECFD0)
#define PTR_ConnectionlessResume REBASE(0x134CE20)
#define PTR_s_Join REBASE(0x156CB6D0)
#define STEAMAPI_STEAMUSER REBASE(0x10B3DC20)
#define STEAMAPI_INTERFACE REBASE(0x10B3DC40)
#define STEAMAPI_FRIENDS REBASE(0x10B3DC20)
#define STEAMAPI_MATCHMAKING REBASE(0x10B3DC30)
#define LOCAL_CLIENT_CONSTATE REBASE(0x5359BC0)
#define Scr_GetNumExpectedPlayers REBASE(0x1ECC770)
// UI_WorldPosToLUIPos 2819320 (needs spoof call)
#define PTR_UI_WorldPosToLUIPos REBASE(0x27A0870)
// CL_ParseSnapshot 1366FF0 (needs spoof call)
#define PTR_CL_ParseSnapshot REBASE(0x1367010)
#define PTR_SV_WriteSnapshotToClient REBASE(0x2205E90)
// linked list entry for setupUITextUncached: 365C718 (const char* name, const subroutine* sub, const __int64 nextEntry)
#define PTR_UI_ToElement REBASE(0x2695400)
//#define SPOOF_GADGET 0x13412B9
//#define SPOOF_TRAMP REBASE(SPOOF_GADGET)
#define PTR_MSG_ReadByte REBASE(0x20FD050)
//#define PTR_MSG_WriteByte REBASE(0x21577C0)
#define PTR_LUIElementFunctionEntryHook REBASE(0x35DD718)
#define PTR_LuaScopedEvent_ctor REBASE(0x1EF8820)
//#define PTR_LuaScoredEvent_dtor REBASE(0x1F04AF0)
//#define PTR_UI_luaVM REBASE(0x19C76D88)
//#define PTR_Lua_SetTableInt REBASE(0x1F066E0)
//#define PTR_Lua_SetTableString REBASE(0x1F06800)
//#define PTR_s_immediateRender REBASE(0x19C76D92)
//#define PTR_UI_Interface_DrawText REBASE(0x1F34920)
//#define PTR_UI_AlignWidgetToScreenPosition REBASE(0x28142F0)
//#define PTR_UI_CustomDrawText REBASE(0x2814F80)
//#define PTR_SvsStaticClients REBASE(0x17906580)
#define PTR_DB_GetAllXAssetOfType REBASE(0x224F840)
//#define PTR_XAssetPool_LuaRawfiles REBASE(0x94C7BA8)
#define PTR_XAssetPool_LuaRawFiles_2 REBASE(0x93889D0)
//#define PTR_hksi_hks_traceback REBASE(0x1D4C960)
#define PTR_hksi_lua_getinfo REBASE(0x1D41500)
#define PTR_luaenginefunction_list REBASE(0x35DD5E0)
#define PTR_getPC REBASE(0x1D39F40)
#define PTR_getFunctionName REBASE(0x1D39400)
#define PTR_hksi_lua_pushfstring REBASE(0x1D35DD0)
//#define PTR_Dvar_Register_Color REBASE(0x22D0920)
//#define PTR_Msg_ClientReliableData_Package REBASE(0x1ED4E60)
//#define PTR_ClientReliableReturn REBASE(0x1EDF620)
//#define PTR_HandleClientReliableData REBASE(0x1EDF590)
#define PTR_Scr_AddInt REBASE(0x12E9890)
//#define PTR_LobbyHostData_GetSession REBASE(0x1EDCDD0)
#define PTR_LiveStats_AreStatsDeltasValid REBASE(0x1E8C570)
#define PTR_LiveStats_DoSecurityChecksCmd REBASE(0x1E8DFE0)
#define PTR_Cmp_TokenizeStringInternal REBASE(0x20E2A3E + 0x3)
//#define PTR_Dvar_CanSetConfigDvar REBASE(0x22B8890)


//#define PTR_Dvar_ValueInDomain REBASE(0x22CB2B0)
//#define PTR_Dvar_CanChangeValue REBASE(0x22B84D0)
//#define DBX_AuthLoad_ValidateSignature_Try REBASE(0x13EC520)
//#define PTR_Jump_ApplySlowdown REBASE(0x2675EE0)
//#define PM_Accelerate_f REBASE(0x260F390)
//#define PM_DoSlideAdjustments_f REBASE(0x268B360)
//#define PM_ClampViewAngles_f REBASE(0x2691700)
//#define PM_CmdScale_f REBASE(0x2611640)
//#define PM_AirMove_f REBASE(0x260F6C0)
//#define Jump_ReduceFriction_f REBASE(0x26767A0)
//#define CL_DrawTextPhysicalWithEffects(text, maxChars, font, x, y, w, xScale, yScale, color, style, glowColor, fxMaterial, fxMaterialGlow, fxBirthTime, fxLetterTime, fxDecayStartTime, fxDecayDuration) ((void(__fastcall*)(const char*, int, __int64, float, float, float, float, float, __int64, int, __int64, __int64, __int64, __int64, __int64, __int64, __int64))REBASE(0x134DDC0))(text, maxChars, font, x, y, w, xScale, yScale, color, style, glowColor, fxMaterial, fxMaterialGlow, fxBirthTime, fxLetterTime, fxDecayStartTime, fxDecayDuration)
//#define UI_DrawTextPadding(localClientNum, scrPlace, text, maxChars, font, x, y, horzAlign, vertAlign, scale, color, style, padding) ((void(__fastcall*)(int, __int64, const char*, int, __int64, float, float, int, int, float, __int64, int, int))REBASE(0x228D100))(localClientNum, scrPlace, text, maxChars, font, x, y, horzAlign, vertAlign, scale, color, style, padding)
// void __cdecl UI_DrawTextPadding(LocalClientNum_t localClientNum, const ScreenPlacement *scrPlace, const char *text, int maxChars, FontHandle font, float x, float y, int horzAlign, int vertAlign, float scale, const vec4_t *color, int style, float padding)
//#define g_zonecount *(__int32*)REBASE(0x941097C)
//#define getframetime() ((unsigned __int32(__fastcall*)())REBASE(0x2332870))()
//#define LobbyNetChan_GetLobbyChannel(lobbyType, lobbyChannel) ((unsigned __int32(__fastcall*)(unsigned __int32, unsigned __int32))REBASE(0x1EF8F20))(lobbyType, lobbyChannel)
//#define LobbyMsgTransport_SendToHostReliably(controllerIndex, lobbySession, destModule, msg, msgType, netchanChannel, msgConfig) ((bool(__fastcall*)(__int32, __int64, LobbyModule, msg_t*, MsgType, __int32, __int32*))REBASE(0x1EF8CA0))(controllerIndex, lobbySession, destModule, msg, msgType, netchanChannel, msgConfig)
//#define Scr_NotifyLevelWithArgs(vm, hash_id, amount) ((void(__fastcall*)(__int32, __int32, __int32, __int32, __int32))REBASE(0x12EC9D0))(vm, *(__int32*)REBASE(0x342155C), *(__int32*)REBASE(0x51A372C), hash_id, amount)
#define PTR_Scr_AddString REBASE(0x12E9A50)
//#define PTR_BG_GetCustomizationTableNameForSessionMode REBASE(0xADDB0)
//#define PTR_Sys_Error REBASE(0x22F4A00)
//#define PTR_CG_UpdatePlayerDObj REBASE(0x98C590)
//#define PTR_CG_UpdatePhysConstraintTags REBASE(0x1F9D70)
//#define PTR_Com_GetClientDObj REBASE(0x214E140)
#define PTR_Scr_AddFloat REBASE(0x12E9780)
#define PTR_getnattype REBASE(0x2887EC0)
//#define PTR_CM_LoadMap REBASE(0x20D8930)
//#define PTR_Com_SessionModeOrCore_GetPath REBASE(0x20F6470)
#define PTR_Scr_AddVec REBASE(0x12E9EB0)
#define PTR_Scr_GetVector REBASE(0x12EBFB0)
//#define PTR_Scr_GetEntity REBASE(0x15F5A50)
//#define PTR_SV_LinkEntity REBASE(0x22633E0)
#define Dvar_FindVar(str_name) ((__int64(__fastcall*)(const char*))REBASE(0x2260870))(str_name)
#define Dvar_GetVariantString(dvar) ((const char*(__fastcall*)(__int64))REBASE(0x2264110))(dvar)
//#define PTR_CM_LinkAllStaticModels REBASE(0x20EAA30)
//#define PTR_R_UseWorld REBASE(0x1C8B1D0)
//#define AxisToAngles(axis, angles) ((void(__fastcall*)(scr_vec3_t*, scr_vec3_t*))REBASE(0x22A52A0))(axis, angles)
//#define AnglesToAxis(angles, axis) ((void(__fastcall*)(scr_vec3_t*, scr_vec3_t*))REBASE(0x22AB140))(angles, axis)
#define Com_Error(type, fmt, ...) ((void(__fastcall*)(__int64, __int32, __int32, const char*, ...))REBASE(0x20EC0B0))((__int64)"", 0, type, fmt, __VA_ARGS__)
#define PTR_Scr_GetWeapon REBASE(0x12EC110)
//#define PTR_WeaponDefVariants (__int64*)REBASE(0x19C73290)
//#define BG_GetNumWeaponsResult (unsigned int)((*(__int32*)REBASE(0x19C74294)) + 1)
//#define PTR_CL_KeyEvent REBASE(0x1342200)
// #define CL_KeyEvent(localclientnum, evt1, evt2, time) ((void(__fastcall*)(__int32, unsigned __int32, unsigned __int32, unsigned __int32))PTR_CL_KeyEvent)(localclientnum, evt1, evt2, time)
//#define PTR_Fire_Weapon REBASE(0x1BBD630)
//#define PTR_GetWeaponDamageForRange1 REBASE(0x26F2BE0)
//#define PTR_Bullet_GetDamage_RETN REBASE(0x1580FF9)
//#define PTR_G_GetWeaponHitLocationMultiplier REBASE(0x19873C0)
//#define PTR_G_GetWeaponHitLocationMultiplier_RETN REBASE(0x1984927)
#define PTR_ScriptErrorHandlers REBASE(0x3277350)
#define PTR_vm_execute REBASE(0x12EDB30)
#define PTR_vm_execute_error_handler REBASE(0x12EE0F0)
//#define PTR_ScrVm_GetFloat REBASE(0x12EB5C0)
//#define ScrVm_GetFloat(inst, indx) ((float(__fastcall*)(__int32, __int32))PTR_ScrVm_GetFloat)(inst, indx)
//#define SPOOFED_CALL(a, ...) spoof_call((void*)SPOOF_TRAMP, a, __VA_ARGS__)
#define OFF_BID_Scr_CastInt REBASE(0x32581A0)
//#define OFF_Dvar_SetFloat REBASE(0x22C6DC0)

const static auto BG_GetAttachmentName = reinterpret_cast<const char* (__fastcall*)(int itemIndex)>(ProcessBase + 0x266FAF0);
const static auto BG_UnlockablesGetClassSetItem = reinterpret_cast<__int64(__fastcall*)(ControllerIndex_t controllerIndex, ClassSetType_t classSetType, int classSetIndex, int loadoutSlot, const char* slotName)>(ProcessBase + 0x262CAC0);
const static auto BG_UnlockablesGetItemAttachmentDisplayName = reinterpret_cast<const char* (__fastcall*)(eModes eMode, int itemIndex, int attachmentNum)>(ProcessBase + 0x262D960);
const static auto BG_UnlockablesGetItemName = reinterpret_cast<const char* (__fastcall*)(eModes eMode, int itemIndex)>(ProcessBase + 0x262E740);
const static auto BG_UnlockablesGetLoadoutSlotFromString = reinterpret_cast<std::uintptr_t(__fastcall*)(const char*)>(ProcessBase + 0x262EC60);
const static auto BG_UnlockablesGetNumItemAttachments = reinterpret_cast<int(__fastcall*)(eModes eMode, int itemIndex)>(ProcessBase + 0x262EE20);
const static auto BG_UnlockablesSetBubbleGumPackName= reinterpret_cast<std::uintptr_t(__fastcall*)(CACRoot* cacRoot, int packIndex, const char* name)>(ProcessBase + 0x2634A20);
const static auto BG_UnlockablesSetClassSetItem = reinterpret_cast<std::uintptr_t(__fastcall*)(ControllerIndex_t controllerIndex, ClassSetType_t classSetType, int classSetIndex, int loadoutSlot, const char* slotName, int itemIndex)>(ProcessBase + 0x2634BF0);
const static auto BG_UnlockablesSetItemIndex = reinterpret_cast<std::uintptr_t(__fastcall*)(CACRoot* CacRoot, __int64 a2, __int64 a3, __int64 itemIndex)>(ProcessBase + 0x16C8A0);
const static auto Cbuf_AddText = reinterpret_cast<std::uintptr_t(__fastcall*)(int, const char*)>(ProcessBase + 0x20DFF50);
const static auto CG_BoldGameMessageCenter = reinterpret_cast<std::uintptr_t(__fastcall*)(int clientNum, const char* msg)>(ProcessBase + 0x8C4C80);
const static auto CG_BulletHitEvent_Internal = reinterpret_cast<__int64(__fastcall*)(int localClientNum, int sourceEntityNum, int targetEntityNum, __int64 weapon, ImVec3 startPos, ImVec3 position, ImVec3 normal, ImVec3 seeThruDecalNormal, int surfType, int* _event, __int64 eventParam, __int16 a12, unsigned __int16 a13, int a14)>(ProcessBase + 0x1189E10);
const static auto CG_Draw2D = reinterpret_cast<void(__fastcall*)(int a1)>(ProcessBase + 0x60F920);
const static auto CL_ConnectionlessCMD = reinterpret_cast<bool(__fastcall*)(int clientNum, netadr_t *from, msg_t *msg)>(ProcessBase + 0x134CD70);
const static auto CL_GetConfigString = reinterpret_cast<const char* (__fastcall*)(int configStringIndex)>(ProcessBase + 0x1321130);
const static auto CL_IsLocalClientInGame = reinterpret_cast<std::uintptr_t(__fastcall*)(int localClientNum)>(ProcessBase + 0x1359900);
const static auto CL_StoreConfigString = reinterpret_cast<const char* (*)(int configStringIndex, const char* string)>(ProcessBase + 0x13667E0);
const static auto Com_IsInGame = reinterpret_cast<bool(*)()>(ProcessBase + 0x20EFF20);
const static auto Com_SessionMode_GetGameMode = reinterpret_cast<eGameModes(__cdecl*)()>(ProcessBase + 0x20EA7F0);
const static auto Com_SessionMode_GetMode = reinterpret_cast<eModes(__cdecl*)()>(ProcessBase + 0x20EAC70);
const static auto Demo_SaveScreenshotToContentServer = reinterpret_cast<void(__fastcall*)(int localClientNum, int fileSlot)>(ProcessBase + 0x2591050);
const static auto Demo_SetMetaData = reinterpret_cast<bool(__fastcall*)(unsigned int a1, __int64 a2, unsigned int a3, __int64 metaDataSize, int a5, char duration)>(ProcessBase + 0x2591590);
const static auto Dvar_SetFromString = reinterpret_cast<std::uintptr_t(__fastcall*)(const char* dvarname, const char* value, bool createifmissing)>(ProcessBase + 0x226B0A0);
const static auto Fileshare_CanDownloadFile = reinterpret_cast<bool(__fastcall*)(unsigned int a1, __int64 ownerXuid, int a3, __int64 fileId, bool isCommunityFile)>(ProcessBase + 0x1E7B060);
const static auto Fileshare_CreateMetaData = reinterpret_cast<bool(__fastcall*)(__int64 a1, FileshareMetaInfo* metaInfo, int* a3, int a4)>(ProcessBase + 0x1DE65C0);
const static auto Fileshare_GetSummaryFileAuthorXUID = reinterpret_cast<uint64_t(__fastcall*)(ControllerIndex_t controllerIndex, uint64_t fileID)>(ProcessBase + 0x1DE9E10);
const static auto flsomeWeirdCharacterIndex = reinterpret_cast<float(__fastcall*)(__int64 a1, int a2, int a3)>(ProcessBase + 0x22C9650);
const static auto G_Damage = reinterpret_cast<__int64(__fastcall*)(__int64 targ, __int64 inflictor, __int64 attacker, __int64 a4, __int64 a5, int a6, int a7, int a8, __int64 a9, int a10, __int64 a11, int a12, int a13, int a14, __int16 a15, int a16, __int64 a17)>(ProcessBase + 0x1980980);
const static auto Game_Message = reinterpret_cast<std::uintptr_t(__fastcall*)(int clientNum, const char* msg)>(ProcessBase + 0x8CB400);
const static auto get_item_infos(eModes mode) { return &reinterpret_cast<item_infos_s*>(ProcessBase + 0x19BABF00)[mode]; }
const static auto I_Strcpy = reinterpret_cast<void(__fastcall*)(BYTE* a1, __int64 a2, const char* a3)>(ProcessBase + 0x227CA00);
const static auto Live_AreWeHost = reinterpret_cast<bool(*)()>(ProcessBase + 0x1E199F0);
const static auto Live_Base_UserGetName = reinterpret_cast<UINT8(__fastcall*)(UINT8 * a1, int a2, char a3)>(ProcessBase + 0x1EA4960);
const static auto Live_IsUserInGame = reinterpret_cast<bool(*)(const int controllerIndex)>(ProcessBase + 0x1E01380);
const static auto Live_IsUserSignedInToDemonware = reinterpret_cast<bool(*)(const ControllerIndex_t)>(ProcessBase + 0x1E013D0);
const static auto Live_UserGetName = reinterpret_cast<bool(__fastcall*)(ControllerIndex_t controllerIndex, char* buf, int bufSize)>(ProcessBase + 0x1EBB200);
const static auto LiveEntitlements_IsEntitlementActiveForController = reinterpret_cast<bool(__fastcall*)(ControllerIndex_t controllerIndex, int incentiveId)>(ProcessBase + 0x1E06110);
const static auto LiveFriends_IsFriendByXUID = reinterpret_cast<bool(__fastcall*)(int controllerIndex, __int64 XUID)>(ProcessBase + 0x1DECFD0);
const static auto LiveInventory_AreExtraSlotsPurchased = reinterpret_cast<bool(__fastcall*)(ControllerIndex_t controllerIndex)>(ProcessBase + 0x1DFC580);
const static auto LiveInventory_GetItemQuantity = reinterpret_cast<__int64(__fastcall*)(ControllerIndex_t controllerIndex, int itemId)>(ProcessBase + 0x1DFCC60);
const static auto LiveInventory_GetPlayerInventory = reinterpret_cast<player_inventory_data_s * (__fastcall*)(ControllerIndex_t controllerIndex)>(ProcessBase + 0x1DFCDD0);
const static auto LiveKeyArchive_SetValueForController = reinterpret_cast<void(__fastcall*)(ControllerIndex_t controllerIndex, dwKeyArchiveCategory category, keyArchiveIndex key, __int64 value, bdArchiveUpdateType updateType)>(ProcessBase + 0x1EB0620);
const static auto LiveKeyArchive_WriteAllCategories = reinterpret_cast<__int64(__fastcall*)(ControllerIndex_t controllerIndex, bool immediate)>(ProcessBase + 0x1EB0760);
const static auto LivePresence_Serialize = reinterpret_cast<__int64(__fastcall*)(__int64 a1, __int64 a2)>(ProcessBase + 0x1E85450);
const static auto LivePresence_Serialize_Crash = reinterpret_cast<UINT8(__fastcall*)(UINT8 * a1, int a2, char a3)>(ProcessBase + 0x1E85450);
const static auto LiveStats_ClassSets_GetClassSetDDLState = reinterpret_cast<bool*(__fastcall*)(DDLState* a1, int a2)>(ProcessBase + 0x1E9CDE0);
const static auto LiveStats_ClassSets_GetClassSetTypeForMode = reinterpret_cast<ClassSetType_t(__fastcall*)( eModes gameMode, eGameModes sessionMode )>(ProcessBase + 0x1E9CE90);
const static auto LiveStats_GetClanName = reinterpret_cast<const char* (__fastcall*)(int controllerIndex)>(ProcessBase + 0x1E90A50);
const static auto LiveStats_GetSelectedItemIndex = reinterpret_cast<unsigned int(__fastcall*)(__int64 controllerIndex, unsigned int mode, unsigned int location, int characterIndex, int ItemType)>(ProcessBase + 0x1E9F050);
const static auto LiveStats_Loadouts_GetCACRoot = reinterpret_cast<CACRoot*(__fastcall*)(CACRoot* CacRoot, int ControllerIndex, int CacType)>(ProcessBase + 0x1EA2CC0);
const static auto LiveStats_Loadouts_GetCACTypeForMode = reinterpret_cast<CACType(__fastcall*)(__int64 sessionMode, __int64 gameMode)>(ProcessBase + 0x1EA2CE0);
const static auto LiveStats_SetClanTagText = reinterpret_cast<std::uintptr_t(__fastcall*)(int, const char*)>(ProcessBase + 0x1E990B0);
const static auto LiveStats_SetClassSetname = reinterpret_cast<bool(__fastcall*)(int controllerIndex, int classSetType, int classSetIndex, const char* classSetName)>(ProcessBase + 0x2634CF0);
const static auto LiveStats_SetIntZombieStatByKey = reinterpret_cast<bool(__fastcall*)(ControllerIndex_t controllerIndex, zombieStatsKeyIndex_t keyIndex, int value)>(ProcessBase + 0x1E99770);
const static auto LiveStats_SetItemColor = reinterpret_cast<bool(__fastcall*)(__int64 a1, __int64 a2, QWORD * a3, int a4, int a5, int a6, int a7, int a8)>(ProcessBase + 0x1EA0280);
const static auto LiveStats_SetSelectedItemColor = reinterpret_cast<bool(__fastcall*)(__int64 controllerIndex, unsigned int mode, unsigned int location, int characterIndex, int ItemType, int itemIndex, int colorSlot, int index)>(ProcessBase + 0x1EA0230);
const static auto LiveStats_SetSelectedItemIndex = reinterpret_cast<bool(__fastcall*)(__int64 controllerIndex, unsigned int mode, unsigned int location, int characterIndex, int ItemType, int index)>(ProcessBase + 0x1EA0A80);
const static auto LiveStats_SetStatByKey = reinterpret_cast<bool(__fastcall*)(eModes mode, ControllerIndex_t controllerIndex, playerStatsKeyIndex_t keyIndex, int value)>(ProcessBase + 0x1E99B80);
const static auto LiveUser_GetXUID = reinterpret_cast<__int64(__fastcall*)(int)>(ProcessBase + 0x1EBAF40);
const static auto LiveUser_GetXuidString = reinterpret_cast<const char* (__fastcall*)(int)>(ProcessBase + 0x1EBAAC0);
const static auto LobbyMsg_HandleIM = reinterpret_cast<std::uintptr_t(__fastcall*)(unsigned int targetController, __int64 senderXuid, void* buff, int len)>(ProcessBase + 0x1EEA130);
const static auto LobbyMsgRW_PackageElement = reinterpret_cast<bool(__fastcall*)(LobbyMsg* lobbyMsg, bool addElement)>(ProcessBase + 0x1EEA320);
const static auto LobbyMsgRW_PrepReadData = reinterpret_cast<bool(__fastcall*)(LobbyMsg*, char*, int)>(ProcessBase + 0x1EEA4F0);
const static auto LobbyMsgRW_PrepReadMsg = reinterpret_cast<bool(__fastcall*)(LobbyMsg*, msg_t*)>(ProcessBase + 0x1EEA520);
const static auto LobbyMsgRW_PrepWriteMsg = reinterpret_cast<bool(__fastcall*)(LobbyMsg*, char*, int, MsgType)>(ProcessBase + 0x1EEA560);
const static auto LobbyMsgRW_ReadArrayBegin = reinterpret_cast<void(__fastcall*)(LobbyMsg*, const char*)>(ProcessBase + 0x1EEA260);
const static auto LobbyMsgRW_ReadString = reinterpret_cast<bool(__fastcall*)(LobbyMsg*, const char* expectedKey, char* a3)>(ProcessBase + 0x227CF30);
const static auto LobbyTypes_GetMainMode = reinterpret_cast<LobbyMainMode(__cdecl*)()>(ProcessBase + 0x1EDFA00);
const static auto Loot_BuyCrate = reinterpret_cast<bool(*)(int ControllerIndex, int CrateType, unsigned int CurrencyType)>(ProcessBase + 0x1E760B0);
const static auto Loot_SpendVials = reinterpret_cast<bool(*)(unsigned int ControllerIndex, int VialNum)>(ProcessBase + 0x1E77490);
const static auto Memset = reinterpret_cast<int(__fastcall*)(char* a1, __int64 a2, unsigned __int64 a3)>(ProcessBase + 0x2BC53B0);
const static auto MSG_BeginReading = reinterpret_cast<void(*)(msg_t*)>(ProcessBase + 0x20FC900);
const static auto MSG_InfoResponse = reinterpret_cast<bool(*)(void*, LobbyMsg*)>(ProcessBase + 0x1ED5B40);
const static auto MSG_InitReadOnly = reinterpret_cast<void(*)(msg_t*, const char*, int)>(ProcessBase + 0x20FCC10);
const static auto MSG_ReadByte = reinterpret_cast<std::uint8_t(*)(msg_t*)>(ProcessBase + 0x20FD050);
const static auto MSG_ReadData = reinterpret_cast<void(*)(msg_t*, void*, int)>(ProcessBase + 0x20FD0B0);
const static auto Msg_ReadStringLine = reinterpret_cast<char*(__fastcall*)(msg_t* msg, char* string, int maxChars)>(ProcessBase + 0x20FED40);
const static auto R_ConvertColorToBytes = reinterpret_cast<void(__fastcall*)(ImVec4 * color, byte * bytes)>(ProcessBase + 0x1D10840);
const static auto SEH_SafeTranslateString = reinterpret_cast<const char* (__fastcall*)(const char* String)>(ProcessBase + 0x221D0B0);
const static auto SetCharacterIndex = reinterpret_cast<bool(__fastcall*)(__int64 ControllerIndex, __int64 eModes, unsigned int CharacterIndex)>(ProcessBase + 0x19E1F0);
const static auto SetGobblegum = reinterpret_cast<std::uintptr_t(__fastcall*)(CACRoot* CacRoot, __int64 packindex, __int64 buffIndex, __int64 itemIndex)>(ProcessBase + 0x2634990);
const static auto Storage_GetDDLContext = reinterpret_cast<DDLContext*(__fastcall*)(unsigned int a1, int a2, int a3)>(ProcessBase + 0x221A640);
const static auto Storage_GetDDLRootState = reinterpret_cast<DDLState*(__fastcall*)(int fileType)>(ProcessBase + 0x221A710);
const static auto Storage_Write = reinterpret_cast<bool(__fastcall*)(int a1, int a2, __int64 a3)>(ProcessBase + 0x221B4F0);
const static auto StringTable_GetAsset = reinterpret_cast<void(__fastcall*)(const char* filename, StringTable * *tablePtr)>(ProcessBase + 0x2251F70);
const static auto StringTable_GetColumnValueForRow = reinterpret_cast<const char* (__fastcall*)(StringTable * table, __int32 row, __int32 column)>(ProcessBase + 0x2252200);
const static auto StringTable_Lookup = reinterpret_cast<const char* (__fastcall*)(StringTable * table, int comparisonColumn, const char* value, int valueColumn)>(ProcessBase + 0x2252390);
const static auto Sys_GetTLS = reinterpret_cast<__int64(__fastcall*)()>(ProcessBase + 0x212B3D0);
const static auto UI_Interface_DrawText = reinterpret_cast<void(__fastcall*)(unsigned int localClientNum, __int64* luiElement, float xPos, float yPos, unsigned int R, unsigned int G,  unsigned int B, unsigned int A, char flags, char* text, __int64 font, float fontHeight, float wrapWidth, float alignment, char luaVM, QWORD * element)>(ProcessBase + 0x1F28860);
const static auto UI_IsRenderingImmediately = reinterpret_cast<bool(__cdecl*)()>(ProcessBase + 0x268CC60);
const static auto UI_SafeTranslateString = reinterpret_cast<const char* (__fastcall*)(const char* String)>(ProcessBase + 0x22328F0);
const static auto UserHasLicenseForApp = reinterpret_cast<char(__fastcall*)(__int64 mapInfo, __int64* userObj)>(ProcessBase + 0x1EAAD60);
const static auto dwInstantDispatchMessage = reinterpret_cast<__int64(__fastcall*)(__int64 SenderId, unsigned int controllerIndex, __int64 msg, unsigned int messageSize)>(ProcessBase + 0x143A620);


// for Offsets.cpp
typedef __int16(__fastcall* CG_DObjGetWorldTagPosInternalT)(__int64 centity_t, __int64 DObj, int tag, float* whatever, float* pos, int something);
typedef __int64(__fastcall* Com_GetClientDObjT)(int a1, int a2);
typedef bool(__fastcall* DDL_GetUIntT)(__int64 result, __int64 a1);
typedef __int64(__fastcall* DDL_MoveToNameT)(__int64 fromState, char* toState, const char* name);
typedef __int64(__fastcall* DDL_MoveToPathT)(__int64 fromState, char* toState, int depth, const char** path);
typedef bool(__fastcall* DDL_Lookup_MoveToNameT)(__int64 fromState, __int64 toState, const char* name);
typedef __int64(__fastcall* DDL_SetIntT)(__int64 result, __int64 a1, int buf);
typedef __int64(__fastcall* DDL_SetStringT)(__int64 result, __int64 a1, const char* string);
typedef __int64(__fastcall* DDL_SetUIntT)(__int64 result, __int64 a1, int buf);
typedef void(__fastcall* GameSendServerCommandT)(int clientNum, int reliable, const char* command);
typedef __int16(__fastcall* GScr_AllocStringT)(const char* s);
typedef int(__fastcall* GetSessionStateT)();
typedef __int64(__fastcall* LiveStats_Core_GetDDLContextT)(unsigned int ControllerIndex, int mode);
typedef __int64(__fastcall* LiveStats_Core_GetStableDDLContextT)(unsigned int ControllerIndex, int mode);
typedef __int64(__fastcall* LiveStats_GetRootDDLStateT)(int statThing);
typedef bool(__fastcall* LiveStats_SetCharacterHeadIndexT)(unsigned int sessionMode, unsigned int statsLocation, DDLContext* ddlContext, unsigned int cacType, unsigned int characterHeadIndex);
typedef bool(__fastcall* LiveStats_SetShowcaseWeaponT)(unsigned int sessionMode, unsigned int statsLocation, DDLContext* ddlContext, unsigned int cacType, unsigned int characterIndex, Variant showcaseWeapon);
typedef __int64(__fastcall* LiveStorage_UploadStatsForControllerT)(int controllerIndex);
typedef bool(__fastcall* LootT)(int controllerIndex, __int64 index, unsigned int incAmount);
typedef __int64(__fastcall* lergstuffT)(int, int);
typedef void(__fastcall* live_presence_pack_t)(presence_data_s* presence, void* buffer, size_t buffer_size);
typedef char* (__fastcall* tGetPersonaName) (DWORD_PTR _this);
typedef __int64(__fastcall* tLiveSteam_FilterPersonaName)(char* buffer, int size, char asciionly);
typedef bool(__fastcall* send_p2p_packet_t)(unsigned __int64 xuid, char type, const void* data, unsigned int cursize);
typedef bool(__fastcall* WorldPosToScreenPosT)(int localClientNum, float* worldPos, float* out);

extern CG_DObjGetWorldTagPosInternalT CG_DObjGetWorldTagPosInternal;
extern Com_GetClientDObjT Com_GetClientDObj;
extern DDL_GetUIntT DDL_GetUInt;
extern DDL_MoveToNameT DDL_MoveToName;
extern DDL_MoveToPathT DDL_MoveToPath;
extern DDL_Lookup_MoveToNameT DDL_Lookup_MoveToName;
extern DDL_SetIntT DDL_SetInt;
extern DDL_SetStringT DDL_SetString;
extern DDL_SetUIntT DDL_SetUInt;
extern DWORD_PTR ISteamFriends;
extern DWORD_PTR iSteamApps;
extern DWORD_PTR iSteamGameServer;
extern DWORD_PTR pGetPersonaNameReturn;
extern GameSendServerCommandT SV_GameSendServerCommand;
extern GetSessionStateT GetSessionState;
extern GScr_AllocStringT GScr_AllocString;
extern LiveStats_Core_GetDDLContextT LiveStats_Core_GetDDLContext;
extern LiveStats_Core_GetStableDDLContextT LiveStats_Core_GetStableDDLContext;
extern LiveStats_GetRootDDLStateT LiveStats_Core_GetRootDDLState;
extern LiveStats_SetCharacterHeadIndexT LiveStats_SetCharacterHeadIndex;
extern LiveStats_SetShowcaseWeaponT LiveStats_SetShowcaseWeapon;
extern LiveStorage_UploadStatsForControllerT LiveStorage_UploadStatsForController;
extern LootT GiveLootToSelf;
extern lergstuffT lergstuff;
extern live_presence_pack_t live_presence_pack;
extern send_p2p_packet_t send_p2p_packet;
extern tGetPersonaName oGetPersonaName;
extern tLiveSteam_FilterPersonaName oLiveSteam_FilterPersonaName;
extern WorldPosToScreenPosT WorldPosToScreenPos;