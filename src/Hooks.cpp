#include "Hooks.h"
#include "overlay.h"     // [LOCAL] overlay::DebugLog for the UI-model path observer below
#include "t7patch_log.h" // [LOCAL] the patch's single runtime log
#include "translate.h"   // [LOCAL] UI string translation layer
#include <cstdarg>
#include <atomic>
#include <cstring>

const char zbr_window_text[] = ZBR_WINDOW_TEXT;
void* pOriginalGSFailure = nullptr;
const char* bad_str = "bad";

namespace hooks {

	// [LOCAL] UI-model path observer (diagnostic, added 2026-09-14).
	//
	// BO3's front-end menus are LUI, and the game resolves them through the UI
	// model tree - these three hooks are the only places the engine tells us
	// which paths it is touching.  Logging each DISTINCT path once turns the
	// overlay log into a record of which screens were built, which is how we
	// hope to find a path that only appears once the real main menu is up (the
	// "press ENTER" screen and the main menu are otherwise indistinguishable
	// from the outside - see the six measured failures in Protection.cpp
	// MainThread).
	//
	// This only WATCHES: nothing here calls game code with arguments of our own
	// invention, and the existing early-outs stay exactly as they were.  Capped
	// and deduplicated, so the log cost is bounded (128 lines per window, once
	// each).  Deliberately lock-free: the hooks can run on different game
	// threads, and the worst case is a duplicated or missing diagnostic line.
	//
	// The budget is per "window": logging only starts once the front-end UI is
	// up (Protection.cpp calls EnableUiModelPathLog(true) on the UI-level edge),
	// because the first launch otherwise spent all 128 entries on the boot-time
	// model construction and recorded nothing about the "press ENTER" -> main
	// menu transition we actually care about.
	constexpr int kUiPathLogMax = 128;
	std::atomic<bool> g_uiModelPathLog{ false };
	int g_uiPathSeenCount = 0;
	const char* g_uiPathSeen[kUiPathLogMax]{};
	char g_uiPathStorage[kUiPathLogMax][64]{};

	// UI text budget (see LogUiString further down).
	constexpr int kUiStringLogMax = 100;
	int g_uiStringSeenCount = 0;
	const char* g_uiStringSeen[kUiStringLogMax]{};
	char g_uiStringStorage[kUiStringLogMax][96]{};

	// Fast path for the LUI menu-name observer: the resolved names are static
	// strings in the game's cache, so an unchanged pointer means nothing new.
	const char* g_lastLuiMenuName = nullptr;

	void EnableUiModelPathLog(bool enable)
	{
		if (!enable)
		{
			g_uiModelPathLog = false;
			return;
		}
		if (!g_uiModelPathLog.exchange(true))
		{
			g_uiPathSeenCount = 0; // fresh budget: boot paths are already logged
			g_uiStringSeenCount = 0;
			g_lastLuiMenuName = nullptr;
		}
	}

	void LogUiModelPath(const char* kind, const char* path)
	{
		if (!g_uiModelPathLog.load() || !path || !path[0])
			return;
		for (int i = 0; i < g_uiPathSeenCount; ++i)
		{
			if (g_uiPathSeen[i] && strcmp(g_uiPathSeen[i], path) == 0)
				return;
		}
		if (g_uiPathSeenCount >= kUiPathLogMax)
			return;

		strncpy_s(g_uiPathStorage[g_uiPathSeenCount],
			sizeof(g_uiPathStorage[0]), path, _TRUNCATE);
		g_uiPathSeen[g_uiPathSeenCount] = g_uiPathStorage[g_uiPathSeenCount];
		++g_uiPathSeenCount;

		char msg[192]{};
		snprintf(msg, sizeof(msg), "uimodel[%s] %s", kind,
			g_uiPathStorage[g_uiPathSeenCount - 1]);
		overlay::DebugLog(msg);
	}

	// [LOCAL] THE screen-detection signal, measured 2026-09-14 23:16: the game
	// resolves these labels exactly when the MAIN MENU renders - the three mode
	// buttons (Campaign / Multiplayer / Zombies) and the quick-join bar.  The
	// title screen only resolves "按ENTER开始" and the connecting screen only
	// "正在连接到在线服务器" / "返回" / "ESC", so seeing one of these means the
	// main menu is on screen (works online and offline - it is pure UI text).
	// The labels are localised, so the Chinese and English wordings are both
	// accepted; the game resolves them at render time, which is what makes this
	// a real screen signal instead of a guess.
	std::atomic<bool> g_mainMenuLabelSeen{ false };

	bool IsMainMenuLabel(const char* text)
	{
		static const char* const kMarkers[] = {
			"多人游戏", "Multiplayer", "MULTIPLAYER",   // mode button
			"僵尸",     "Zombies",     "ZOMBIES",       // mode button
			"战役",     "Campaign",    "CAMPAIGN",      // mode button
			"QUICK JOIN",                               // quick-join bar (untranslated)
			"服务器浏览器", "Server Browser",
		};
		for (const char* marker : kMarkers)
		{
			if (strstr(text, marker))
				return true;
		}
		return false;
	}

	bool UiMainMenuSeen()
	{
		return g_mainMenuLabelSeen.load();
	}

	// [LOCAL] Second diagnostic: the UI text the game is building right now.
	// The front-end renders different strings on the title screen and in the
	// main menu, so a distinctive label appearing here would be a genuine
	// "which screen is showing" signal (unlike the UI-model tree, which the
	// front-end builds on a timer while the title screen is still up).
	// (State declared next to the path-log budget above.)
	void LogUiString(const char* kind, const char* text)
	{
		if (!text || !text[0])
			return;

		// [LOCAL] Screen detection first - it must work whether or not the
		// verbose UI diagnostics are switched on.
		if (!g_mainMenuLabelSeen.load() && IsMainMenuLabel(text))
		{
			g_mainMenuLabelSeen = true;
			char msg[160]{};
			snprintf(msg, sizeof(msg), "gate: main-menu label rendered (%s)", text);
			overlay::DebugLog(msg);
		}

		if (!g_uiModelPathLog.load())
			return;
		for (int i = 0; i < g_uiStringSeenCount; ++i)
		{
			if (g_uiStringSeen[i] && strcmp(g_uiStringSeen[i], text) == 0)
				return;
		}
		if (g_uiStringSeenCount >= kUiStringLogMax)
			return;

		strncpy_s(g_uiStringStorage[g_uiStringSeenCount],
			sizeof(g_uiStringStorage[0]), text, _TRUNCATE);
		g_uiStringSeen[g_uiStringSeenCount] = g_uiStringStorage[g_uiStringSeenCount];
		++g_uiStringSeenCount;

		char msg[160]{};
		snprintf(msg, sizeof(msg), "uistring[%s] %s", kind,
			g_uiStringStorage[g_uiStringSeenCount - 1]);
		overlay::DebugLog(msg);
	}

	// [LOCAL] Second observer: the LUI menu-name lookup.  Whatever maps a menu
	// index to a name sees every LUI menu the front-end opens, so the sequence
	// of names is the closest thing to "which screen is showing" we can get
	// without reverse-engineering the LUI state global.  Log-only: the value is
	// always whatever the game's own function returned (the bounds guard the
	// original (disabled) hook had is deliberately not applied here, matching
	// today's behaviour where this hook is not installed at all).
	void LogLuiMenuName(unsigned int index, const char* name)
	{
		if (!g_uiModelPathLog.load() || !name || !name[0])
			return;
		if (name == g_lastLuiMenuName)
			return;
		g_lastLuiMenuName = name;

		char msg[160]{};
		snprintf(msg, sizeof(msg), "luimenu[index=%u] %s", index, name);
		overlay::DebugLog(msg);
	}

	namespace functions
	{

		__int64 hkLiveInventory_GetItemQuantity(ControllerIndex_t controllerIndex, int itemId) {

			#if SPOOF_UNLOCK_ALL
				// Source: /gamedata/loot/zmlootitems.csv
				if (itemId >= 1000000010 && itemId < 1000000200) {
					return SPOOF_GUM_COUNT;
				} else {
					return 1;
				}
			#endif

			return LiveInventory_GetItemQuantity(controllerIndex, itemId);
		}

		bool hkLiveInventory_AreExtraSlotsPurchased(ControllerIndex_t controllerIndex) {
		
			#if SPOOF_UNLOCK_ALL
				return true;
			#endif

			return LiveInventory_AreExtraSlotsPurchased(controllerIndex);
		}

		const char* hkInfo_ValueForKey(char* a1, __int64 a2) {
			return Info_ValueForKey(a1, a2);
		}
		// Caused uninstalled content to show as available.
		bool hkLiveInventory_IsValid(ControllerIndex_t controllerIndex) {

			#if SPOOF_UNLOCK_ALL
			return true;
			#endif

			return LiveInventory_IsValid(controllerIndex);
		}

		// Source: /gamedata/store/common/incentives.csv
		bool hkLiveEntitlements_IsEntitlementActiveForController(ControllerIndex_t controllerIndex, int incentiveId) {

			#if SPOOF_UNLOCK_ALL

				// Invalid / Duplicates
				if (incentiveId == 29 || incentiveId == 30 || incentiveId == 34) {
					return false;
				}

				#if SPOOF_SKIP_CWL

					if (incentiveId == 21 || incentiveId == 22 || incentiveId == 23) {
						return false;
					}

				#endif

				return true;

			#endif

			return LiveEntitlements_IsEntitlementActiveForController(controllerIndex, incentiveId);
		}

		bool hkUserHasLicenseForApp(__int64 mapInfo, __int64* userObj) {
			#if SPOOF_UNLOCK_ALL
				if (userObj)
				{
					*((BYTE*)userObj + 13) = 1;
					*((BYTE*)userObj + 12) |= 0;
					*((DWORD*)userObj + 4) |= 8u;
				}
				return true;
			#endif

			return UserHasLicenseForApp(mapInfo, userObj);
		}

		const char* hkBG_Cache_GetScriptMenuNameForIndex(unsigned int inst, unsigned int index)
		{
			if (index >= 64u)
				return bad_str;

			return BG_Cache_GetScriptMenuNameForIndex(inst, index);
		}

		const char* hkBG_Cache_GetEventStringNameForIndex(unsigned int inst, unsigned int index)
		{
			if (index >= 256u)
				return bad_str;

			return BG_Cache_GetEventStringNameForIndex(inst, index);
		}

		const char* hkBG_Cache_GetLocStringNameForIndex(unsigned int inst, unsigned int index)
		{
			if (index >= 2048u)
				return bad_str;

			return BG_Cache_GetLocStringNameForIndex(inst, index);
		}

		const char* hkBG_Cache_GetLUIMenuForIndex(unsigned int inst, unsigned int index)
		{
			// [LOCAL] Log-only observer - see LogLuiMenuName.  The game's own
			// result is always returned unchanged, so installing this hook cannot
			// alter menu behaviour.  The out-of-bounds guard the old body had
			// (index >= 64 -> "bad") is deliberately NOT applied: this hook was
			// not installed before, so the guard was inactive as well, and
			// restoring it here could break any caller that legitimately passes a
			// larger index (that decision belongs to upstream).
			const char* name = BG_Cache_GetLUIMenuForIndex(inst, index);
			LogLuiMenuName(index, name);
			return name;
		}

		const char* __fastcall hkBG_Cache_GetLUIMenuDataForIndex(unsigned int inst, unsigned int index)
		{
			if (index >= 128u)
				return bad_str;

			return BG_Cache_GetLUIMenuDataForIndex(inst, index);
		}

		void hkLiveInvites_AcceptInvite(UINT controllerIndex, DWORD* message, __int64 recepientXUID) // Prevent non-friends from 'pulling' us into lobbies.
		{
			if (Protection::IsFriendsOnly)
			{
				if (!Protection::IsFriendByXUIDUncached(recepientXUID))
				{
					return;
				}
			}
			return LiveInvites_AcceptInvite(controllerIndex, message, recepientXUID);
		}

		void hkLiveInvites_JoinMessageAction(UINT controllerIndex, DWORD* message, __int64 recepientXUID) // Prevent non-friends from 'pulling' us into lobbies.
		{
			if (Protection::IsFriendsOnly)
			{
				if (!Protection::IsFriendByXUIDUncached(recepientXUID))
				{
					return;
				}
			}
			return LiveInvites_JoinMessageAction(controllerIndex, message, recepientXUID);
		}

		__int64 hkLiveInvites_SendJoinInfo(UINT controllerIndex, __int64 recepientXUID, __int64 a3) // Prevent non-friends from 'pulling' us into lobbies.
		{
			if (Protection::IsFriendsOnly)
			{
				if (!Protection::IsFriendByXUIDUncached(recepientXUID))
				{
					return 0;
				}
			}

			return LiveInvites_SendJoinInfo(controllerIndex, recepientXUID, a3);

		}

		char hkUI_BrowserOpen(__int64 a1)
		{
			return 0;
		}

		bool hkLive_UserGetName(ControllerIndex_t controllerIndex, char* buf, int bufSize) {

			__int64 v3; // rbx
			int* v6; // rax
			int v9; // [rsp+40h] [rbp+8h] BYREF

			v3 = bufSize;
			v9 = bufSize;
			Memset(buf, 0i64, bufSize);
			v6 = &v9;

			Live_Base_UserGetName((UINT8*)buf, *v6, 1);

			return 1;
		}

		float hkflsomeWeirdCharacterIndex(__int64 a1, int a2, int a3) {

			__int64 v3; // r9

			v3 = *(DWORD64*)(a1 + 24i64 * a2 + 56);
			if (v3) {
				return flsomeWeirdCharacterIndex(a1, a2, a3);
			}

			return -1.0f;

		}

		bool hkCL_ConnectionlessCMD(int clientNum, netadr_t* from, msg_t* msg) {

			auto v7 = *(int**)(Sys_GetTLS() + 24);
			auto v8 = *v7;
			auto message = **(CHAR***)&v7[2 * v8 + 34];

			// From v2.04
			auto mode = Com_SessionMode_GetModeName();

			if ((!Protection::I_stricmp(message, "requeststats") || !Protection::I_stricmp(message, "requeststats\n")) && !Protection::I_stricmp(mode, "CP"))
			{
				return CL_ConnectionlessCMD(clientNum, from, msg);
			}

			// Filter packets, only allow legit packets through, block the rest
			if (is_in_array(message, legit_packets)) {
				return CL_ConnectionlessCMD(clientNum, from, msg);
			}

			return 1;
		}
		
		const char* __fastcall hkCL_GetConfigString(std::int32_t configStringIndex)
		{

			constexpr auto mspreload_command = "mspreload";
			std::vector<int> config_strings = { 3514, 3627 };

			auto mode = Com_SessionMode_GetModeName();
			if (mode && !Protection::I_stricmp(mode, "CP"))
			{
				return CL_GetConfigString(configStringIndex);
			}

			if (is_in_number_array(configStringIndex, config_strings))
			{
				if (auto config_string{ CL_GetConfigString(configStringIndex) }; is_equal(config_string, mspreload_command, std::strlen(mspreload_command), false))
				{
					// Loadside attempt caught, return empty string to prevent crash
					CL_StoreConfigString(configStringIndex, "");
				}
			}

			return CL_GetConfigString(configStringIndex);
		}

		void hkLobbyMsgRW_PrintMessage()
		{
			// do nothing, bugged function
		}

		__int32 hkLobbyMsgRW_PrintDebugMessage()
		{
			return 0;
		}

		void hkExecLuaCMD()
		{
			// do nothing, bugged function
		}

		const char* hkSEH_ReplaceDirectiveInStringWithBinding(int localClientNum, const char* translatedString, char* finalString)
		{
			char input[4096];

			if (!translatedString)
			{
				translatedString = "";
			}

			if (strlen(translatedString) > 4095)
			{
				return 0;
			}

			if (!finalString)
			{
				return 0;
			}

			strcpy_s(input, translatedString);
			input[4095] = 0;
			LogUiString("seh", translatedString); // [LOCAL] screen-content probe

			// [LOCAL] UI translation layer.  Whole-string exact match only: a
			// miss leaves the original text untouched, so a partial match can
			// never corrupt unrelated UI text.  Collect() runs first and stores
			// the ENGLISH source (it skips strings that already carry non-ASCII
			// bytes), then the dictionary replaces it for display.
			translate::Collect(input);
			if (translate::Enabled())
			{
				char translated[4096] = {};
				if (translate::Lookup(input, translated, sizeof(translated)))
					strcpy_s(input, translated);
			}
			int max = (int)strlen(input);

			for (int i = 0; i < max; i++)
			{
				if (input[i] != '^' || (i + 1) >= max)
				{
					continue;
				}
				if (input[i + 1] != 'B')
				{
					continue;
				}
				bool b_found = false;
				int j = i + 2;
				int count = 0;
				for (; j < max; j++, count++)
				{
					if (input[j] == '^')
					{
						b_found = true;
						if (count >= 0x40)
						{
							b_found = false;
						}
						break;
					}
				}
				if (!b_found)
				{
					input[i] = '.';
					i++;
				}
				else
				{
					i = j;
				}
			}

			auto tokenPos = strstr(input, "[{");
			while (tokenPos)
			{
				auto endTokenPos = strstr(tokenPos + 2, "}]");
				if (!endTokenPos || (endTokenPos - tokenPos) >= 0x100)
				{
					*tokenPos = '.';
					*(tokenPos + 1) = '.';
				}
				tokenPos = strstr(tokenPos + 2, "[{");
			}

			return SEH_ReplaceDirectiveInStringWithBinding(localClientNum, input, finalString);
		}

		__int64 hkqmemcpy(char* dest, char* source, __int32 size)
		{
			if (size < 0)
			{
				*dest = 0;
				// [LOCAL] removed "*source = 0": source is the buffer we read FROM
				// and can live in read-only memory; writing it is an access violation.
				return 0;
			}
			return qmemcpy(dest, source, size);
		}

		bool hkUI_DoModelStringReplacement(__int32 controllerIndex, char* element, const char* source, char* dest, unsigned int destSize)
		{
			// [LOCAL] The two guards its twin, hkSEH_ReplaceDirectiveInString-
			// WithBinding, has had all along: a null source, and a source that
			// cannot fit the fixed 4096-byte local.  Without them strcpy_s (the
			// MSVC array overload, which knows the destination size) invokes the
			// invalid-parameter handler, i.e. _invoke_watson / terminate in a
			// release build.  A UI string that long can only come from a corrupt
			// or oversized localisation entry - which is exactly the input this
			// hook exists to defend against.
			char input[4096]{};

			if (!source)
			{
				source = "";
			}

			if (strlen(source) > 4095)
			{
				return false; // refuse rather than truncate: same policy as the twin
			}

			strcpy_s(input, source);
			input[4095] = 0;
			LogUiString("model", source); // [LOCAL] screen-content probe

			// [LOCAL] Same translation layer as the SEH hook above - see the
			// comment there; the two functions are the whole front-end string
			// pipeline, which is why the dictionary covers mods as well.
			translate::Collect(input);
			if (translate::Enabled())
			{
				char translated[4096] = {};
				if (translate::Lookup(input, translated, sizeof(translated)))
					strcpy_s(input, translated);
			}
			int max = (int)strlen(input);

			bool b_replace = false;
			for (int i = 0; i < max; i++)
			{
				if (input[i] != '$' || (i + 1) >= max)
				{
					continue;
				}
				if (input[i + 1] != '(')
				{
					continue;
				}
				bool b_found = false;
				int j = i + 2;
				for (; j < max; j++)
				{
					if (input[j] == ')')
					{
						b_found = true;
						break;
					}
				}
				if (!b_found)
				{
					b_replace = true;
					input[i] = '.';
					input[i + 1] = '.';
					i++;
				}
				else
				{
					i = j;
				}
			}

			if (b_replace)
			{
				strcpy_s(dest, destSize, input);
				*(dest + destSize - 1) = 0;
				return true;
			}

			return UI_DoModelStringReplacement(controllerIndex, element, input, dest, destSize);
		}

		const char* hkLobbyTypes_GetMsgTypeName(__int32 index)
		{
			if (index < -1)
			{
				return "invalid";
			}

			if (index > MESSAGE_TYPE_DEMO_STATE)
			{
				if (index >= MESSAGE_TYPE_ZBR_COUNT)
				{
					return "invalid";
				}

				return "invalid";
			}

			return LobbyTypes_GetMsgTypeName(index);
		}		
		
		__int64 hkSys_VerifyPacketChecksum(const char* payload, __int32 payloadLen)
		{
			if (payloadLen >= 2)
			{
				auto newLen = payloadLen - 2;
				auto checksum = (unsigned __int16)Protection::PrivatePassword[1] ^ Sys_Checksum((unsigned __int8*)payload, payloadLen - 2);
				if (*(unsigned __int16*)(newLen + payload) == (unsigned __int16)checksum)
				{
					return newLen;
				}
				else
				{
					// check if the last time we updated the private password was within the past second
					if (GetTickCount64() <= (ULONGLONG)Protection::PrivatePassword[2] + 1500) // [LOCAL] C4018: compare in unsigned tick space
					{
						checksum = checksum ^ (unsigned __int16)Protection::PrivatePassword[1] ^ (unsigned __int16)Protection::PrivatePassword[0];
						if (*(unsigned __int16*)(newLen + payload) == (unsigned __int16)checksum)
						{
							return newLen;
						}
					}
				}
				//ALOG("^6Dropping packet checksum %d != %d\n\n\n\n", checksum, *(__int16*)(newLen + payload));
			}
			return -1;
		}

		unsigned __int16 hkSys_ChecksumCopy(const char* desta, const char* srca, __int32 length) {
			auto val = Sys_ChecksumCopy(desta, srca, length);
			/*if ((*(__int32*)(LOCAL_CLIENT_CONSTATE + 8) >= 0xB))
			{
				val ^= (__int16)Protection::PrivatePassword[1];
			}*/
			val ^= (unsigned __int16)Protection::PrivatePassword[1];
			return val;
		}

		void __report_gsfailure_hook(__int64 security_cookie) { *(__int64*)(0x17) = 0; };

		const char* hkCOD_GetBuildTitle()
		{
			return zbr_window_text;
		}

		void hkLiveSteam_InitServer() 
		{
			return;
		}

		bool hkLive_SystemInfo(int controllerIndex, int infoType, char* outputString, const int outputLen)
		{
			if (infoType)
			{
				return Live_SystemInfo(controllerIndex, infoType, outputString, outputLen);
			}
			strcpy_s(outputString, outputLen, ZBR_VERSION_FULL);
			return true;
		}

		bool Global_InstantMessage(uintptr_t thisptr, unsigned __int64 sender_id, const char* sender_name, uintptr_t msg, unsigned int size)
		{
			return false; // Block all instant messages from this source
		}

		__int64 hkdwInstantDispatchMessage(__int64 senderXuid, unsigned int controllerIndex, const char* message, unsigned int messageSize)
		{
			msg_t msg{};
			MSG_InitReadOnly(&msg, message, messageSize);
			MSG_BeginReading(&msg);

			bool is_valid_packet = true;
			BYTE packetType = 0;

			if (MSG_ReadByte(&msg) == '1')
			{
				packetType = MSG_ReadByte(&msg);
			}

			char* msgData = *(char**)(message + 8);
			__int32 msgSize = *(__int32*)(message + 0x1C);
			__int32 msgRead = *(__int32*)(message + 0x24);
			const auto remainingSize = msgSize - msgRead;

			// check packet for the following cases:
			if (packetType == 0x65 || packetType == 0x6D) // cbuf
			{
				is_valid_packet = false;
			}
			else if (packetType == 0x66) // is a joinRequest
			{		
				if ((msgSize - msgRead) != 0x64) // has a bad message size which leads to error message
				{
					is_valid_packet = false;
				}

				char* packetData = msgData + msgRead;
				if (is_valid_packet && !*(__int32*)packetData) // msg_type_join_request which leads to crash
				{
					is_valid_packet = false;
				}
			}

			if (is_valid_packet && (packetType == 0x68) && Protection::CheckPendingInfoRequests(senderXuid, (msg_t*)message))
			{
				return 0;
			}

			if (is_valid_packet)
			{
				if (const auto size{ msg.cursize - msg.readcount }; size < 2048u)
				{
					char data[2048] = { 0 };
					MSG_ReadData(&msg, data, size);
					return LobbyMsg_HandleIM(0, senderXuid, data, size);
				}
				
			}

			return 0;
		}

		__int64 __fastcall hkLivePresence_Serialize(__int64 a1, __int64 a2)
		{
			if (!a1 || !a2)
				return 0;

			int* packedPtr = *reinterpret_cast<int**>(a1 + 16);

			if (!packedPtr)
				return 0;

			int packed = *packedPtr;
			int count = (packed >> 2) & 0x1F;

			constexpr int maxPlayers = 18;

			if (count > maxPlayers)
			{
				int sanitized = packed;

				sanitized &= ~(0x1F << 2);
				sanitized |= (maxPlayers & 0x1F) << 2;

				*packedPtr = sanitized;
			}

			return LivePresence_Serialize(a1, a2);
		}

		bool hkLobbyMsgRW_PrepWriteMsg(__int64 lobbyMsg, __int64 data, int length, int msgType)
		{
			if (LobbyMsgRW_PrepWriteMsg(lobbyMsg, data, length, msgType))
			{
				// ALOG("sending pkt %d", msgType);
				if (ZBR_PREFIX_BYTE)
				{
					((void(__fastcall*)(__int64, unsigned char))PTR_MSG_WriteByte)(lobbyMsg, ZBR_PREFIX_BYTE);
					((void(__fastcall*)(__int64, unsigned char))PTR_MSG_WriteByte)(lobbyMsg, ZBR_PREFIX_BYTE2);
				}
				return true;
			}
			return false;
		}

		bool hkLobbyMsgRW_PrepReadMsg(__int64 lm)
		{
			// [LOCAL] Consumes the optional two-byte ZBR prefix that
			// hkLobbyMsgRW_PrepWriteMsg prepends when a private-room password is
			// configured, so the payload that follows starts where the reader
			// expects it.
			//
			// Every path returns true on purpose - rejecting here is NOT safe.
			// The lobby stream also carries traffic from clients that never
			// wrote a prefix (anyone not running the patch), and dropping those
			// desynchronises the lobby.  So a prefix mismatch means "not from a
			// patched peer", not "malformed": the message is still passed on.
			// The original function's result is ignored for that same reason.
			//
			// The previous form, "if (A && (...)) return true; return true;",
			// behaved identically but read as though the check mattered, with
			// the ReadByte side effects buried in a condition whose value was
			// thrown away.
			const bool primed = LobbyMsgRW_PrepReadMsg(lm);
			if (primed && ZBR_PREFIX_BYTE)
			{
				// [LOCAL] The second read is CONDITIONAL, not a second skip.
				// The original expression was "readByte() == BYTE && readByte()
				// == BYTE2", and && short-circuits: when the first byte does not
				// match, the second read never happens.  Each read advances the
				// message cursor, so that one-byte difference is visible to
				// whatever parses the payload after this call.  Keep the exact
				// shape - only the side effects matter, the values are unused.
				const unsigned char firstByte =
					((unsigned char(__fastcall*)(__int64))PTR_MSG_ReadByte)(lm);
				if (firstByte == ZBR_PREFIX_BYTE)
				{
					(void)(((unsigned char(__fastcall*)(__int64))PTR_MSG_ReadByte)(lm));
				}
			}

			return true;
		}

		bool hkLobbyMsgRW_PackageInt(LobbyMsg* lobbyMsg, const char* key, __int32* val)
		{
			
			bool result = LobbyMsgRW_PackageInt(lobbyMsg, key, val);

			if (result && (!Protection::I_stricmp(key, "lobbytype") || !Protection::I_stricmp(key, "srclobbytype") || !Protection::I_stricmp(key, "destlobbytype")))
			{

				if (*val < LOBBY_TYPE_FIRST || *val > LOBBY_TYPE_LAST)
				{
					//XLOG("DROP LOBBYTYPE");
					return false;
				}
			}
			return result;
		}

		bool hkLobbyMsgRW_PackageUInt(LobbyMsg* lobbyMsg, const char* key, unsigned __int32* val)
		{
			bool result = LobbyMsgRW_PackageUInt(lobbyMsg, key, val);
			if (result && (!Protection::I_stricmp(key, "lobbytype") || !Protection::I_stricmp(key, "srclobbytype") || !Protection::I_stricmp(key, "destlobbytype")))
			{
				if (*val > static_cast<unsigned __int32>(LOBBY_TYPE_LAST))
				{
					return false;
				}
			}
			if (result && (!Protection::I_stricmp(key, "datamask")))
			{
				__int32 state = *(__int32*)REBASE(0x1686E874);
				state = state << 28 >> 28;
				if (state)
				{
					return result;
				}
				return !(*val & 512);
			}
			return result;
		}

		bool hkLobbyMsgRW_PackageUChar(LobbyMsg* lobbyMsg, const char* key, unsigned char* val)
		{
			bool result = LobbyMsgRW_PackageUChar(lobbyMsg, key, val);
			if (result && !Protection::I_stricmp(key, "nattype"))
			{
				if (*val > 4) // 4 is "unknown" which is the highest valid nat type
				{
					*val = 4;
				}
			}
			return result;
		}

		void hkCMD_MenuReponse_f(char* ent)
		{
			char mres[1024]{};
			char szMenuName[1024]{};

			// cant call original cause arxan pointer decryption routines, but its fine we can just recreate and omit some other useless stuff while we are at it.
			int nesting = *(__int32*)REBASE(0x1681BEB0); // REBASE(0x1689AE94)
			int num_args = ((__int32*)REBASE(0x1681BF14))[nesting];
			int menuIndex = 0;

			if (num_args != 4)
			{
				strcpy_s(mres, "bad");
			}
			else
			{
				SV_Cmd_ArgvBuffer(1, szMenuName, 1024);
				auto svId = atoi(szMenuName);
				if (svId != *(__int32*)REBASE(0x17679580))
				{
					return; // unamused
				}
				SV_Cmd_ArgvBuffer(2, szMenuName, 1024);
				menuIndex = atoi(szMenuName);
				if ((unsigned __int32)menuIndex > 0x3Fu)
				{
					szMenuName[0] = 0;
				}
				else
				{
					strcpy_s(szMenuName, BG_Cache_GetScriptMenuNameForIndex(0, menuIndex));
				}
				SV_Cmd_ArgvBuffer(3, mres, 1024);
			}

			if (!Protection::I_stricmp(mres, "badspawn"))
			{
				return;
			}

			if (*(__int32*)ent) // not host
			{
				if (!(Protection::I_stricmp(mres, "killserverpc") && Protection::I_stricmp(mres, "endgame") && Protection::I_stricmp(mres, "endround") && Protection::I_stricmp(mres, "restart_level_zm")))
				{
					// someone who is not host tried to end the game
					snprintf(mres, 1024, "tempBanClient %i\n", *(__int32*)ent); // kick them
					Protection::Cbuf_AddText(0, mres, 0);
					return;
				}
			}

			if (Protection::I_stricmp(mres, "killserverpc") && Protection::I_stricmp(mres, "endgame") && Protection::I_stricmp(mres, "endround")
				|| LobbyHost_IsHost(1u))
			{
				Scr_AddString(0, mres);
				Scr_AddString(0, szMenuName);
				__int32 thread = Scr_ExecEntThread(ent, (void*)*(__int64*)REBASE(0xA5A6810), 2);
				Scr_FreeThread(0, thread);
			}
			else
			{
				// someone who is not host tried to end the game
				snprintf(mres, 1024, "tempBanClient %i\n", *(__int32*)ent); // kick them
				Protection::Cbuf_AddText(0, mres, 0);
				return;
			}

		}

		void hk_CMD_MenuResponseCached_f(char* ent)
		{
			char mres[1024]{};
			char szMenuName[1024]{};

			// cant call original cause arxan pointer decryption routines, but its fine we can just recreate and omit some other useless stuff while we are at it.
			int nesting = *(__int32*)REBASE(0x1681BEB0);
			int num_args = ((__int32*)REBASE(0x1681BF14))[nesting];
			int menuIndex = 0;

			if (num_args != 4)
			{
				strcpy_s(mres, "bad");
			}
			else
			{
				SV_Cmd_ArgvBuffer(1, szMenuName, 1024);
				auto svId = atoi(szMenuName);
				if (svId != *(__int32*)REBASE(0x17679580))
				{
					return; // unamused
				}
				SV_Cmd_ArgvBuffer(2, szMenuName, 1024);
				menuIndex = atoi(szMenuName);
				if ((unsigned __int32)menuIndex > 0x3Fu)
				{
					szMenuName[0] = 0;
				}
				else
				{
					strcpy_s(szMenuName, BG_Cache_GetScriptMenuNameForIndex(0, menuIndex));
				}
				SV_Cmd_ArgvBuffer(3, mres, 1024);
				auto eventIndex = (unsigned int)atoi(mres);
				strcpy_s(mres, BG_Cache_GetEventStringNameForIndex(0, eventIndex));
			}

			if (!Protection::I_stricmp(mres, "badspawn"))
			{
				return;
			}

			if (*(__int32*)ent) // not host
			{
				if (!(Protection::I_stricmp(mres, "killserverpc") && Protection::I_stricmp(mres, "endgame") && Protection::I_stricmp(mres, "endround") && Protection::I_stricmp(mres, "restart_level_zm")))
				{
					// someone who is not host tried to end the game
					snprintf(mres, 1024, "tempBanClient %i\n", *(__int32*)ent); // kick them
					Protection::Cbuf_AddText(0, mres, 0);
					return;
				}
			}

			if (Protection::I_stricmp(mres, "killserverpc") && Protection::I_stricmp(mres, "endgame") && Protection::I_stricmp(mres, "endround")
				|| LobbyHost_IsHost(1u))
			{
				Scr_AddString(0, mres);
				Scr_AddString(0, szMenuName);
				__int32 thread = Scr_ExecEntThread(ent, (void*)*(__int64*)REBASE(0xA5A6810), 2);
				Scr_FreeThread(0, thread);
			}
			else
			{
				// someone who is not host tried to end the game
				snprintf(mres, 1024, "tempBanClient %i\n", *(__int32*)ent); // kick them
				Protection::Cbuf_AddText(0, mres, 0);
				return;
			}
		}

		__int32 hkUI_Model_GetModelFromPath_0(__int64 parentNodeIndex, const char* path)
		{
			if (!path)
			{
				return 0;
			}
			int len = (int)strlen(path);
			int keySize = 0;
			for (int i = 0; i < len; i++)
			{
				if (path[i] != '.')
				{
					keySize++;
				}
				else
				{
					if (keySize >= 64)
					{
						return 0;
					}
					keySize = 0;
				}
			}
			if (keySize >= 64)
			{
				return 0;
			}
			LogUiModelPath("get0", path);
			return UI_Model_GetModelFromPath_0(parentNodeIndex, path);
		}

		__int32 hkUI_Model_GetModelFromPath(__int64 parentNodeIndex, const char* path)
		{
			if (!path)
			{
				return 0;
			}
			int len = (int)strlen(path);
			int keySize = 0;
			for (int i = 0; i < len; i++)
			{
				if (path[i] != '.')
				{
					keySize++;
				}
				else
				{
					if (keySize >= 64)
					{
						return 0;
					}
					keySize = 0;
				}
			}
			if (keySize >= 64)
			{
				return 0;
			}
			LogUiModelPath("get", path);
			return UI_Model_GetModelFromPath(parentNodeIndex, path);
		}

		__int32 hkUI_Model_CreateModelFromPath(__int64 parentNodeIndex, const char* path)
		{
			if (!path)
			{
				return 0;
			}
			int len = (int)strlen(path);
			int keySize = 0;
			for (int i = 0; i < len; i++)
			{
				if (path[i] != '.')
				{
					keySize++;
				}
				else
				{
					if (keySize >= 64)
					{
						return 0;
					}
					keySize = 0;
				}
			}
			if (keySize >= 64)
			{
				return 0;
			}
			LogUiModelPath("create", path);
			return UI_Model_CreateModelFromPath(parentNodeIndex, path);
		}

		__int32 hkUI_Model_AllocateNode(__int32 ancestorIndex, const char* path, bool persistent)
		{
			if (!path)
			{
				return 0;
			}
			if (!*(__int16*)REBASE(0x16293150)) // out of model paths to use (TODO: should we instead back this off and restart the UI?)
			{
				return 0;
			}
			if (strlen(path) >= 64)
			{
				return 0;
			}
			LogUiModelPath("alloc", path);
			return UI_Model_AllocateNode(ancestorIndex, path, persistent);
		}

		bool hkMods_SubscribeUGC(__int64 a1)
		{			
			return false;
		}				
	}

	// [LOCAL] 46-block fallback-hook state, shared by InstallD3DCompilerBlock()
	// and ApplyHooks().  At hooks-namespace level so ApplyHooks can restore the
	// intended state after its MH_ALL_HOOKS sweep (which would otherwise
	// silently re-enable a hook that the config says must stay off; that
	// flag/hook divergence then made the first menu toggle fail).
	volatile LONG g_block46Created = 0;
	volatile LONG g_block46Enabled = 0;
	void* g_block46Target = nullptr;

	void ApplyVMTHooks()
	{

		auto ptr = *(uintptr_t*)DW_LOBBY;
		auto vmt = **(uintptr_t***)(ptr + 1384);

		auto vtable_buf = new uintptr_t[50];
		for (auto count = 0; count < 50; ++count) {
			vtable_buf[count] = vmt[count];
		}

		**(uintptr_t**)(ptr + 1384) = (uintptr_t)vtable_buf;
		*(uintptr_t*)(**(uintptr_t**)(ptr + 1384) + 192) = (uintptr_t)functions::Global_InstantMessage;

	}

	void ApplyMemoryPatches()
	{
		auto OldProtection = 0ul;
		// SL fix (nop out the calls to com_error)
		VirtualProtect((__int32*)REBASE(0x1964766), 5, PAGE_EXECUTE_READWRITE, &OldProtection);
		*(__int32*)REBASE(0x1964766) = 0x90909090;
		*(char*)(REBASE(0x1964766) + 4) = 0x90;
		VirtualProtect((__int32*)REBASE(0x1964766), 5, OldProtection, &OldProtection);

		// SL fix (nop out the calls to com_error)
		VirtualProtect((__int32*)REBASE(0x19646A7), 5, PAGE_EXECUTE_READWRITE, &OldProtection);
		*(__int32*)REBASE(0x19646A7) = 0x90909090;
		*(char*)(REBASE(0x19646A7) + 4) = 0x90;
		VirtualProtect((__int32*)REBASE(0x19646A7), 5, OldProtection, &OldProtection);

		VirtualProtect((__int32*)REBASE(0x1EEACF2), 4, PAGE_EXECUTE_READWRITE, &OldProtection);
		*(char*)REBASE(0x1EEACF2 + 1) = 0xB7; // fix movsx issue with package readglob
		VirtualProtect((__int32*)REBASE(0x1EEACF2), 4, OldProtection, &OldProtection);

		VirtualProtect((__int32*)PTR_Cmp_TokenizeStringInternal, 1, PAGE_EXECUTE_READWRITE, &OldProtection);
		*(char*)PTR_Cmp_TokenizeStringInternal = 0x2F;
		VirtualProtect((__int32*)PTR_Cmp_TokenizeStringInternal, 1, OldProtection, &OldProtection);

		// process priority
		VirtualProtect((__int32*)REBASE(0x22BC1CD), 4, PAGE_EXECUTE_READWRITE, &OldProtection);
		*(__int32*)REBASE(0x22BC1CD) = 0x00008000; // above normal
		VirtualProtect((__int32*)REBASE(0x22BC1CD), 4, OldProtection, &OldProtection);

		VirtualProtect((__int32*)REBASE(0x22BC1D2), 4, PAGE_EXECUTE_READWRITE, &OldProtection);
		*(__int32*)REBASE(0x22BC1D2) = 0x00008000; // above normal
		VirtualProtect((__int32*)REBASE(0x22BC1D2), 4, OldProtection, &OldProtection);

		// movsx -> movzx
		VirtualProtect((__int32*)REBASE(0x1F21EF8), 1, PAGE_EXECUTE_READWRITE, &OldProtection);
		*(char*)REBASE(0x1F21EF8) = 0xb6;
		VirtualProtect((__int32*)REBASE(0x1F21EF8), 1, OldProtection, &OldProtection);

		// movsx -> movzx
		VirtualProtect((__int32*)REBASE(0x1CA4C84), 1, PAGE_EXECUTE_READWRITE, &OldProtection);
		*(char*)REBASE(0x1CA4C84) = 0xb6;
		VirtualProtect((__int32*)REBASE(0x1CA4C84), 1, OldProtection, &OldProtection);
	}

	void ApplyHooks()
	{
		MH_CreateHook((LPVOID)REBASE(0x1EEA560), functions::hkLobbyMsgRW_PrepWriteMsg, (LPVOID*)&LobbyMsgRW_PrepWriteMsg);
		MH_CreateHook((LPVOID)REBASE(0x1EEB8D0), functions::hkLobbyMsgRW_PrepReadMsg, (LPVOID*)&LobbyMsgRW_PrepReadMsg);
		MH_CreateHook((LPVOID)REBASE(0x20E31C0), functions::hkCOD_GetBuildTitle, (LPVOID*)&COD_GetBuildTitle);
		MH_CreateHook((LPVOID)REBASE(0x1E016C0), functions::hkLive_SystemInfo, (LPVOID*)&Live_SystemInfo);
		MH_CreateHook((LPVOID)REBASE(0x1EDFA60), functions::hkLobbyTypes_GetMsgTypeName, (LPVOID*)&LobbyTypes_GetMsgTypeName);
		MH_CreateHook((LPVOID)REBASE(0x2BC4EB0), functions::hkqmemcpy, (LPVOID*)&qmemcpy);
		MH_CreateHook((LPVOID)REBASE(0x22C9650), functions::hkflsomeWeirdCharacterIndex, (LPVOID*)&flsomeWeirdCharacterIndex);
		MH_CreateHook((LPVOID)REBASE(0x221CE90), functions::hkSEH_ReplaceDirectiveInStringWithBinding, (LPVOID*)&SEH_ReplaceDirectiveInStringWithBinding);
		MH_CreateHook((LPVOID)REBASE(0x1EEA3E0), functions::hkLobbyMsgRW_PackageInt, (LPVOID*)&LobbyMsgRW_PackageInt);
		MH_CreateHook((LPVOID)REBASE(0x1EEA490), functions::hkLobbyMsgRW_PackageUInt, (LPVOID*)&LobbyMsgRW_PackageUInt);
		MH_CreateHook((LPVOID)REBASE(0x1EEA450), functions::hkLobbyMsgRW_PackageUChar, (LPVOID*)&LobbyMsgRW_PackageUChar);
		MH_CreateHook((LPVOID)REBASE(0x1F27400), functions::hkUI_DoModelStringReplacement, (LPVOID*)&UI_DoModelStringReplacement);
		MH_CreateHook((LPVOID)REBASE(0x1EA9C80), functions::hkLiveSteam_InitServer, (LPVOID*)&LiveSteam_InitServer);
		MH_CreateHook((LPVOID)REBASE(0x195F100), functions::hkCMD_MenuReponse_f, (LPVOID*)&CMD_MenuResponse_f);
		MH_CreateHook((LPVOID)REBASE(0x195EFA0), functions::hk_CMD_MenuResponseCached_f, (LPVOID*)&CMD_MenuResponseCached_f);
		MH_CreateHook((LPVOID)REBASE(0x200CF00), functions::hkUI_Model_GetModelFromPath_0, (LPVOID*)&UI_Model_GetModelFromPath_0);
		MH_CreateHook((LPVOID)REBASE(0x200D5B0), functions::hkUI_Model_GetModelFromPath, (LPVOID*)&UI_Model_GetModelFromPath);
		MH_CreateHook((LPVOID)REBASE(0x200CFC0), functions::hkUI_Model_CreateModelFromPath, (LPVOID*)&UI_Model_CreateModelFromPath);
		MH_CreateHook((LPVOID)REBASE(0x200CD00), functions::hkUI_Model_AllocateNode, (LPVOID*)&UI_Model_AllocateNode);
		MH_CreateHook((LPVOID)REBASE(0x211F5A0), functions::hkSys_VerifyPacketChecksum, (LPVOID*)&Sys_VerifyPacketChecksum);
		MH_CreateHook((LPVOID)REBASE(0x211F500), functions::hkSys_ChecksumCopy, (LPVOID*)&Sys_ChecksumCopy);
		MH_CreateHook((LPVOID)REBASE(0x1EEA940), functions::hkLobbyMsgRW_PrintMessage, (LPVOID*)&LobbyMsgRW_PrintMessage);
		MH_CreateHook((LPVOID)REBASE(0x1EEA680), functions::hkLobbyMsgRW_PrintDebugMessage, (LPVOID*)&LobbyMsgRW_PrintDebugMessage);
		MH_CreateHook((LPVOID)REBASE(0x1EF8A60), functions::hkExecLuaCMD, (LPVOID*)&ExecLuaCMD);
		MH_CreateHook((LPVOID)REBASE(0x1EBB200), functions::hkLive_UserGetName, (LPVOID*)&Live_UserGetName);
		MH_CreateHook((LPVOID)&__report_gsfailure, functions::__report_gsfailure_hook, (LPVOID*)&pOriginalGSFailure);
		MH_CreateHook((LPVOID)REBASE(0x143A620), functions::hkdwInstantDispatchMessage, (LPVOID*)&dwInstantDispatchMessage);
		MH_CreateHook((LPVOID)REBASE(0x134CD70), functions::hkCL_ConnectionlessCMD, (LPVOID*)&CL_ConnectionlessCMD);
		MH_CreateHook((LPVOID)REBASE(0x1E85450), functions::hkLivePresence_Serialize, (LPVOID*)&LivePresence_Serialize);
		MH_CreateHook((LPVOID)REBASE(0x1321130), functions::hkCL_GetConfigString, (LPVOID*)&CL_GetConfigString);
		MH_CreateHook((LPVOID)REBASE(0x20CB0C0), functions::hkMods_SubscribeUGC, (LPVOID*)&Mods_SubscribeUGC);
		MH_CreateHook((LPVOID)REBASE(0x1E19B30), functions::hkLiveInvites_AcceptInvite, (LPVOID*)&LiveInvites_AcceptInvite);
		MH_CreateHook((LPVOID)REBASE(0x1E724A0), functions::hkLiveInvites_SendJoinInfo, (LPVOID*)&LiveInvites_SendJoinInfo);
		MH_CreateHook((LPVOID)REBASE(0x1E72040), functions::hkLiveInvites_JoinMessageAction, (LPVOID*)&LiveInvites_JoinMessageAction);
		MH_CreateHook((LPVOID)REBASE(0x1EA4E30), functions::hkUI_BrowserOpen, (LPVOID*)&UI_BrowserOpen);
		/*MH_CreateHook((LPVOID)REBASE(0xA7DE0), functions::hkBG_Cache_GetScriptMenuNameForIndex, (LPVOID*)&BG_Cache_GetScriptMenuNameForIndex);
		MH_CreateHook((LPVOID)REBASE(0xA78A0), functions::hkBG_Cache_GetEventStringNameForIndex, (LPVOID*)&BG_Cache_GetEventStringNameForIndex);
		MH_CreateHook((LPVOID)REBASE(0xA7AB0), functions::hkBG_Cache_GetLocStringNameForIndex, (LPVOID*)&BG_Cache_GetLocStringNameForIndex);
		MH_CreateHook((LPVOID)REBASE(0xA7990), functions::hkBG_Cache_GetLUIMenuDataForIndex, (LPVOID*)&BG_Cache_GetLUIMenuDataForIndex);*/
		// [LOCAL] BG_Cache_GetLUIMenuForIndex was hooked here (log-only observer,
		// see LogLuiMenuName) to find out which LUI menu the front-end opens.  It
		// never fired: measured on 2026-09-14 the whole front-end navigation runs
		// without it, so it belongs to the in-game script menu system instead.
		// Left unhooked (matches upstream) - the log-only implementation is kept
		// for whoever needs it for that other system.
		MH_CreateHook((LPVOID)REBASE(0x1EAAD60), functions::hkUserHasLicenseForApp, (LPVOID*)&UserHasLicenseForApp);
		MH_CreateHook((LPVOID)REBASE(0x1DFCC60), functions::hkLiveInventory_GetItemQuantity, (LPVOID*)&LiveInventory_GetItemQuantity);
		MH_CreateHook((LPVOID)REBASE(0x1E06110), functions::hkLiveEntitlements_IsEntitlementActiveForController, (LPVOID*)&LiveEntitlements_IsEntitlementActiveForController);
		MH_CreateHook((LPVOID)REBASE(0x1DFC580), functions::hkLiveInventory_AreExtraSlotsPurchased, (LPVOID*)&LiveInventory_AreExtraSlotsPurchased);
		MH_CreateHook((LPVOID)REBASE(0x1DFDFE0), functions::hkLiveInventory_IsValid, (LPVOID*)&LiveInventory_IsValid);
		MH_CreateHook((LPVOID)REBASE(0x227BDA0), functions::hkInfo_ValueForKey, (LPVOID*)&Info_ValueForKey);

		MH_EnableHook(MH_ALL_HOOKS);

		// [LOCAL] The ALL_HOOKS sweep also (re-)enabled the LoadLibraryExW
		// fallback hook that InstallD3DCompilerBlock() deliberately left
		// disabled when the config says so.  Restore the intended state here,
		// otherwise the flag says "off" while the hook is live and the first
		// menu toggle fails with MH_ERROR_ENABLED.
		if (g_block46Created && g_block46Target && g_block46Enabled == 0)
			MH_DisableHook(g_block46Target);
	}

	void DestroyHooks()
	{
		MH_DisableHook(MH_ALL_HOOKS);
	}

	// [LOCAL] ============================================================
	// Legacy shader-compiler blocker - FALLBACK LAYER.
	//
	// The mechanism that actually does the job now lives in Protection.cpp:
	// the switch renames <game>\d3dcompiler_46.dll to
	// <game>\d3dcompiler_46.dll.bak (and renames it back when the switch is
	// off), so the engine cannot find the file at all.  This hook is kept as a
	// second line of defence for what a rename cannot cover: a read-only game
	// folder, or the file being put back by hand while the game is running.
	//
	// Corrected 2026-09-15: the comment that used to stand here claimed the
	// engine "falls back to the modern D3DCompiler_47 pipeline" once the load
	// is refused.  That was never measured and it is wrong.  The
	// D3DCompiler_47 seen in the process comes from OUR OWN import table
	// (imgui compiles its pipeline shaders with D3DCompile - see
	// imgui/backends/imgui_impl_dx11.cpp), while the game itself neither
	// imports nor requests any d3dcompiler.  Four measured sessions logged
	// this hook as armed and never firing a single time, and the file was
	// never opened or mapped by the game.  Only a "block #N" log line is
	// proof that this hook ever did anything.
	// ============================================================
	static HMODULE(WINAPI* fpLoadLibraryExW)(LPCWSTR lpLibFileName, HANDLE hFile, DWORD dwFlags) = nullptr;
	static volatile LONG d3dc_block_count = 0;

	// [LOCAL] One line into the patch's single log (t7patch_log.h), tagged
	// "block".  Used both for install diagnostics and for every intercepted
	// load, so the user can verify the feature without any external tooling.
	static void d3dc_block_write_log(const char* fmt, ...)
	{
		char text[512] = {};
		va_list ap;
		va_start(ap, fmt);
		_vsnprintf_s(text, sizeof(text), _TRUNCATE, fmt, ap);
		va_end(ap);

		t7log::Append("block", text);
	}

	static bool contains_legacy_d3dcompiler(const wchar_t* s)
	{
		if (!s)
			return false;

		const wchar_t needle[] = L"d3dcompiler_46";
		const int nlen = 14;

		for (const wchar_t* p = s; *p; ++p)
		{
			int i = 0;
			while (i < nlen)
			{
				wchar_t a = p[i];
				wchar_t b = needle[i];
				if (a >= L'A' && a <= L'Z')
					a += (L'a' - L'A');
				if (a != b)
					break;
				++i;
			}
			if (i == nlen)
				return true;
		}
		return false;
	}

	static HMODULE WINAPI hkLoadLibraryExW(LPCWSTR lpLibFileName, HANDLE hFile, DWORD dwFlags)
	{
		if (contains_legacy_d3dcompiler(lpLibFileName))
		{
			InterlockedIncrement(&d3dc_block_count);
			OutputDebugStringA("[T7Patch] blocked d3dcompiler_46.dll load (legacy shader compiler stutter fix)\n");

			// [LOCAL] Verification log: the user checks this file to confirm the
			// block actually fires in-game, no DebugView required.
			d3dc_block_write_log("block #%d: \"%ls\" (flags=0x%X)",
				(int)d3dc_block_count, lpLibFileName, dwFlags);

			SetLastError(ERROR_MOD_NOT_FOUND);
			return NULL; // report "not found" (see the note above)
		}
		return fpLoadLibraryExW(lpLibFileName, hFile, dwFlags);
	}

	// [LOCAL] Dynamic 46-block state for the overlay menu:
	//   created - the MinHook entry exists (created once, early)
	//   enabled - calls actually land in hkLoadLibraryExW right now
	//   target  - kernel32!LoadLibraryExW (fixed for the process lifetime)
		// [LOCAL] 46-block hook state now lives at namespace level (above).

	void InstallD3DCompilerBlock()
	{
		// Create the hook once.  Whether it starts ENABLED follows the config
		// (block_d3dcompiler46, default 0 since 2026-09-16); the overlay menu
		// can flip it later at runtime without re-hooking.
		static volatile LONG create_started = 0;
		if (InterlockedCompareExchange(&create_started, 1, 0) != 0)
			return;

		HMODULE k32 = GetModuleHandleA("kernel32.dll");
		void* target = k32 ? (void*)GetProcAddress(k32, "LoadLibraryExW") : nullptr;
		if (!target)
		{
			OutputDebugStringA("[T7Patch] LoadLibraryExW not found - d3dcompiler block NOT installed\n");
			d3dc_block_write_log("install FAILED: LoadLibraryExW not found");
			return;
		}
		g_block46Target = target;

		// The game loads the patch during process startup (static import of
		// d3d11.dll), so this may run before RunPatching() - make sure MinHook
		// is initialised here too.  A later MH_Initialize() inside RunPatching()
		// simply returns MH_ERROR_ALREADY_INITIALIZED and is harmless.
		MH_STATUS init = MH_Initialize();
		if (init != MH_OK && init != MH_ERROR_ALREADY_INITIALIZED)
		{
			d3dc_block_write_log("install FAILED: MH_Initialize rc=%d", (int)init);
			return;
		}

		MH_STATUS rc = MH_CreateHook(target, (LPVOID)&hkLoadLibraryExW, (LPVOID*)&fpLoadLibraryExW);
		if (rc != MH_OK)
		{
			OutputDebugStringA("[T7Patch] MH_CreateHook(LoadLibraryExW) failed - d3dcompiler block NOT installed\n");
			d3dc_block_write_log("install FAILED: MH_CreateHook rc=%d", (int)rc);
			return;
		}
		g_block46Created = 1;

		if (t7patch_block_d3dcompiler46_enabled())
		{
			MH_EnableHook(target);
			g_block46Enabled = 1;
			OutputDebugStringA("[T7Patch] d3dcompiler_46 block installed\n");
			d3dc_block_write_log("block armed (hook installed on LoadLibraryExW)");
		}
		else
		{
			g_block46Enabled = 0;
			d3dc_block_write_log("hook created but disabled by config (block_d3dcompiler46=0)");
		}
	}

	// [LOCAL] Menu-side toggle.  Two layers, and the order matters:
	//   1. the file move (Protection.cpp) - this is what changes what the
	//      engine can see, and it is the only reason the switch does anything;
	//   2. the LoadLibraryExW hook above, kept as a fallback.
	// The move runs even when the hook was never created (MinHook failure) or
	// is already in the wanted state, and the config is written either way, so
	// the next launch reconciles to the same state.
	void SetD3DCompilerBlock(bool enable)
	{
		t7patch_config_set_block46(enable);

		if (!t7patch_d3dcompiler46_hide_file(enable))
			d3dc_block_write_log("46 file: requested state NOT applied - see the line above");

		if (g_block46Created && enable != (g_block46Enabled != 0))
		{
			MH_STATUS rc = enable ? MH_EnableHook(g_block46Target) : MH_DisableHook(g_block46Target);
			if (rc == MH_ERROR_ENABLED || rc == MH_ERROR_DISABLED)
			{
				// [LOCAL] The hook was already in the wanted state (e.g. the
				// ALL_HOOKS sweep re-enabled it behind our back).  Treat as
				// success and re-sync the flag.  A divergence here must NOT
				// skip the config save below: the file rename is the layer
				// that works, and the persisted switch is what the next
				// launch's reconcile follows - skipping it made the rename
				// silently revert on restart.
				g_block46Enabled = enable ? 1 : 0;
				d3dc_block_write_log("toggle: hook already %s, flag re-synced",
					enable ? "enabled" : "disabled");
			}
			else if (rc != MH_OK)
			{
				// [LOCAL] Log only - the save below still runs.
				d3dc_block_write_log("toggle FAILED rc=%d", (int)rc);
			}
			else
			{
				g_block46Enabled = enable ? 1 : 0;
				d3dc_block_write_log(enable ? "block ENABLED from menu" : "block DISABLED from menu");
			}
		}

		t7patch_config_save();
	}

	bool IsD3DCompilerBlockEnabled()
	{
		// [LOCAL] The checkbox shows the SETTING, not the hook state.  The
		// hook is only the fallback layer and may legitimately not exist
		// (MinHook failure) while the file move still does the job; echoing
		// the hook state here would draw the switch as "off" while it works.
		return t7patch_block_d3dcompiler46_enabled();
	}

	int GetD3DCompilerBlockCount()
	{
		return d3dc_block_count;
	}

}
