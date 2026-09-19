#include "Protection.h"
#include "Hooks.h"   // [LOCAL] EnableUiModelPathLog (UI-model path observer)
#include "overlay.h" // [LOCAL] NotifyMainMenuReached (menu_auto_open timing)
#include "t7patch_log.h" // [LOCAL] the 46-file renames go to the patch's single log
#include "translate.h"   // [LOCAL] UI translation layer (dictionary reload hook)

#include <mutex>  // [LOCAL] guards the config object, friends_set and dlcContent
#include <atomic> // [LOCAL] the config apply hand-off flag (menu Save -> MainThread)

bool has_set_window_text = false;
bool Protection::IsFriendsOnly = false;
bool Protection::IsInjectorlessInstall = true;
__int64 Protection::PrivatePassword[3] = { 0, 0 };
char Protection::CustomName[16] = { 0 };
std::unordered_map<BYTE, std::function<void(__int32* lobbyMsgTypePtr, __int64 lobbyMsg)>> Protection::handle_packet_callbacks;
__int64 Protection::Old_lobbymsgprints = NULL;
__int64 Protection::CachedRetnAddy = NULL;
__int64 Protection::CachedXUID = NULL;
tZwContinue Protection::ZwContinue = NULL;
tI_stricmp Protection::I_stricmp = NULL;
char* Protection::UILocalizeDefaultText = NULL;
tLobbyMsgRW_PackageInt Protection::LobbyMsgRW_PackageInt = NULL;
tLobbyMsgRW_PackageUChar Protection::LobbyMsgRW_PackageUChar = NULL;
tLobbyMsgRW_PackageString Protection::LobbyMsgRW_PackageString = NULL;
tLobbyMsgRW_PackageXuid Protection::LobbyMsgRW_PackageXuid = NULL;
tLobbyMsgRW_PackageBool Protection::LobbyMsgRW_PackageBool = NULL;
tLobbyMsgRW_PackageUInt Protection::LobbyMsgRW_PackageUInt = NULL;
tLobbyMsgRW_PackageShort Protection::LobbyMsgRW_PackageShort = NULL;
tLobbyMsgRW_PackageUInt64 Protection::LobbyMsgRW_PackageUInt64 = NULL;
tLobbyMsgRW_PackageArrayStart Protection::LobbyMsgRW_PackageArrayStart = NULL;
tLobbyMsgRW_PackageElement Protection::LobbyMsgRW_PackageElement = NULL;
tLobbyMsgRW_PackageGlob Protection::LobbyMsgRW_PackageGlob = NULL;
tMsgMutableClientInfo_Package Protection::MsgMutableClientInfo_Package = NULL;
tProbeLobbyInfo Protection::ProbeLobbyInfo = NULL;
tdwInstantHandleLobbyMessage Protection::dwInstantHandleLobbyMessage = NULL;
tNET_OutOfBandPrint Protection::NET_OutOfBandPrint = NULL;
tdwCommonAddrToNetadr Protection::dwCommonAddrToNetadr = NULL;
tdwRegisterSecIDAndKey Protection::dwRegisterSecIDAndKey = NULL;
tLobbyMsgRW_PrepWriteMsg Protection::LobbyMsgRW_PrepWriteMsg = NULL;
tLobbyMsgRW_PackageUShort Protection::LobbyMsgRW_PackageUShort = NULL;
tLobbyMsgRW_PackageFloat Protection::LobbyMsgRW_PackageFloat = NULL;
tMSG_Init Protection::MSG_Init = NULL;
tMSG_WriteString Protection::MSG_WriteString = NULL;
tMSG_WriteShort Protection::MSG_WriteShort = NULL;
tMSG_WriteByte Protection::MSG_WriteByte = NULL;
tMSG_WriteData Protection::MSG_WriteData = NULL;
tCom_ControllerIndex_GetLocalClientNum Protection::Com_ControllerIndex_GetLocalClientNum = NULL;
tCom_LocalClient_GetNetworkID Protection::Com_LocalClient_GetNetworkID = NULL;
tNET_OutOfBandData Protection::NET_OutOfBandData = NULL;
tLobbyMsgTransport_SendToAdr Protection::LobbyMsgTransport_SendToAdr = NULL;
tMSG_ReadData Protection::MSG_ReadData = NULL;
tLobbyMsgRW_PrepReadData Protection::LobbyMsgRW_PrepReadData = NULL;
tMSG_InfoResponse Protection::MSG_InfoResponse = NULL;
tLobbyMsgRW_PackageChar Protection::LobbyMsgRW_PackageChar = NULL;
tdwInstantSendMessage Protection::dwInstantSendMessage = NULL;
tLobbySession_GetControllingLobbySession Protection::LobbySession_GetControllingLobbySession = NULL;
tLobbySession_GetSession Protection::LobbySession_GetSession = NULL;
tLobbySession_GetClientByClientNum Protection::LobbySession_GetClientByClientNum = NULL;
tLobbySession_GetClientNetAdrByIndex Protection::LobbySession_GetClientNetAdrByIndex = NULL;
tLobbyJoin_Reserve Protection::LobbyJoin_Reserve = NULL;
tCL_GetConfigString Protection::CL_GetConfigString = NULL;
tCbuf_AddText Protection::Cbuf_AddText = NULL;

const char* sMstart;
const char* sMdata;
const char* sMhead;
const char* sMstate;
const char* sConnectResponse;
const char* sRcon;
const char* sRequestStats;
const char* sRequestStats2;
const char* sLoading;
const char* sRA;
const char* sV;
const char* sVT;
const char* sRelay;
const char* sLMGI;

SD(targetlobby)
SD(sourcelobby)
SD(jointype)
SD(probedxuid)
SD(playlistid)
SD(playlistver)
SD(ffotdver)
SD(networkmode)
SD(netchecksum)
SD(protocol)
SD(changelist)
SD(pingband)
SD(dlcbits)
SD(joinnonce)
SD(chunk)
SD(isStarterPack)
SD(password)
SD(membercount)
SD(members)
SD(xuid)
SD(lobbyid)
SD(skillrating)
SD(skillvariance)
SD(pprobation)
SD(aprobation)
SD(statenum)
SD(mainmode)
SD(partyprivacy)
SD(lobbytype)
SD(lobbymode)
SD(sessionstatus)
SD(uiscreen)
SD(leaderactivity)
SD(key)
SD(leader)
SD(platformsession)
SD(maxclients)
SD(isadvertised)
SD(clientcount)
SD(sessionid)
SD(sessioninfo)
SD(ugcName)
SD(ugcVersion)
SD(clientlist)
SD(clientNum)
SD(gamertag)
SD(isGuest)
SD(connectbit)
SD(score)
SD(address)
SD(qport)
SD(band)
SD(netsrc)
SD(joinorder)
SD(dlcBits)
SD(migratebits)
SD(lasthosttimems)
SD(nomineelist)
SD(serverstatus)
SD(launchnonce)
SD(matchhashlow)
SD(matchhashhigh)
SD(status)
SD(statusvalue)
SD(gamemode)
SD(gametype)
SD(map)
SD(cpqueuedlevel)
SD(movieskipped)
SD(team)
SD(mapvote)
SD(readyup)
SD(plistid)
SD(plistcurr)
SD(plistentries)
SD(plistnext)
SD(plistprev)
SD(plistprevcount)
SD(votecount)
SD(votes)
SD(itemtype)
SD(item)
SD(itemgroup)
SD(attachment)
SD(votetype)
SD(votexuid)
SD(pregamepos)
SD(pregamestate)
SD(clvotecount)
SD(character)
SD(loadout)
SD(settingssize)
SD(compstate)
SD(heartbeatnum)
SD(nonce)
SD(nattype)
SD(lobbies)
SD(valid)
SD(hostxuid)
SD(hostname)
SD(secid)
SD(seckey)
SD(addrbuff)

EXPORT void SetFriendsOnly(bool isFriendsOnly)
{
    Protection::IsFriendsOnly = isFriendsOnly;
}

EXPORT void SetPlayerName(const char* name)
{
    if (strlen(name) > 15)
    {
        return;
    }
    memset(Protection::CustomName, 0, sizeof(Protection::CustomName));
    strcpy_s(Protection::CustomName, name);
    Protection::CustomName[sizeof(Protection::CustomName) - 1] = 0;

    // [LOCAL] An empty name means "leave the game's own name alone".  Writing an
    // empty string into these two game buffers would instead blank the name out
    // everywhere that reads them, so only touch them for a real custom name.
    // Note: clearing a name that was set earlier in the same session leaves the
    // previous value in those buffers until the next game start, which is when
    // this function first sees the empty name.  The Steam paths below still
    // revert immediately.
    if (*Protection::CustomName)
    {
        strncpy_s((char*)(pUserData + 0x8), 16, Protection::CustomName, sizeof(Protection::CustomName));
        strncpy_s((char*)(pNameBuffer), 16, Protection::CustomName, sizeof(Protection::CustomName));

        // [LOCAL] Mirror the start-up write (see Protection::install()).  Those
        // four locations hold strings the front-end has ALREADY built, and that
        // is exactly why renaming from the menu used to need a game restart:
        // install() wrote them once at start-up, this runtime path never did, so
        // the Steam hooks answered with the new name while the UI kept drawing
        // the old one out of its own copy.
        //
        // Same four targets as the start-up pass, and the same byte count
        // (strlen+1, at most 16, since a name longer than 15 is rejected above).
        // No new address is touched and no longer write happens, so this is no
        // riskier than the pass that has always run in install().
        const size_t nameBytes = strlen(Protection::CustomName) + 1;
        memcpy((void*)REBASE(0x15E84638), Protection::CustomName, nameBytes);
        memcpy((void*)PTR_Name1, Protection::CustomName, nameBytes);
        memcpy((void*)PTR_Name2, Protection::CustomName, nameBytes);
        if (!Protection::IsBadReadPtr((VOID*)s_playerData_ptr) && *(INT64*)s_playerData_ptr)
        {
            memset((void*)(*(INT64*)s_playerData_ptr + 0x8), 0, 16);
            memcpy((void*)(*(INT64*)s_playerData_ptr + 0x8), Protection::CustomName, nameBytes);
        }

        // [LOCAL] One line per apply.  It answers, from the log alone, whether a
        // name edit reached the engine at all - the other half of "I changed my
        // name and the game still shows the old one".
        char nameMsg[96]{};
        snprintf(nameMsg, sizeof(nameMsg),
            "playername applied to the front-end strings (%u bytes)", (unsigned)nameBytes);
        overlay::DebugLog(nameMsg);
    }
}

EXPORT void SetNetworkPassword(const char* pass)
{
    // [LOCAL] NULL guard.  This is reached from apply_settings() with whatever
    // the config object holds at that instant, and the config watcher runs on
    // another thread - the stored pointer used to be freed and reallocated
    // there, so NULL was reachable and the very first statement (strlen) would
    // dereference it.  The old condition, "strlen(pass) == 0 || !(*pass)", was
    // also one test written twice: both spell "empty string".
    if (pass == nullptr || *pass == '\0')
    {
        Protection::SetNetworkPassword(0);
    }
    else
    {
        Protection::SetNetworkPassword(GSCUHashing::canon_hash64(pass));
    }
}

IHOOK_HEADER(IsProcessorFeaturePresent, BOOL, (DWORD processorFeature))
{
    if (processorFeature == 0x17)
    {
        // force a crash
        *(__int64*)0x17 = processorFeature;
        *(__int64*)processorFeature = 0x17;
    }
    return IHOOK_ORIGINAL(IsProcessorFeaturePresent, (processorFeature));
}

bool Protection::ReadP2PPacket(uintptr_t thisptr, void* pub_dest, unsigned int cub_dest, unsigned int* cub_msg_size, unsigned __int64* steam_id_remote, int n_channel) {

	bool result = ((bool(__fastcall*)(uintptr_t, void*, unsigned int, unsigned int*, uint64_t*, int))GetOriginalSteamPtr(STEAMAPI_NETWORKING, STEAMAPI_NETWORKING_READP2PPACKET))(thisptr, pub_dest, cub_dest, cub_msg_size, steam_id_remote, n_channel);

    if (result && cub_msg_size && *cub_msg_size > 5) {

        char* data = reinterpret_cast<char*>(pub_dest);

        auto game_im = data[5];

        if (game_im == 104) // info request
        {
            if (Protection::IsFriendsOnly && !Protection::IsFriendByXUIDUncached(*steam_id_remote)) {
                return false;
            }
        }

        if (game_im == 102) // join request
        {
            return false;
        }

        if (game_im == 101 || game_im == 109) // cbuf
        {
            return false;
        }
    }

    return result;
}

const char* Protection::GetUsernamePtr(INT64 a)
{
    // [LOCAL] With no custom name configured, hand the real Steam persona name
    // back to the game instead of blanking it out.
    if (!CustomName[0])
    {
        auto original = (const char* (__fastcall*)(INT64))GetOriginalSteamPtr(
            STEAMAPI_STEAMUSER, STEAMAPI_STEAMUSER_GETUSERNAME);

        if (original)
        {
            return original(a);
        }
        return "";
    }

    return CustomName;
}

unsigned __int64 next_update_friendslist_time = 0;
std::unordered_set<__int64> friends_set;
// [LOCAL] friends_set is read from Steam-callback/game threads and rebuilt every
// 30s. It used to be clear()+insert()'ed in place with no lock, so concurrent
// readers could observe an empty set (friends treated as non-friends) or crash
// on a rehash mid-find. Now: rebuild into a local set, then swap under the lock.
std::mutex friends_set_mutex;
bool Protection::IsFriendByXUIDUncached(__int64 xuid) // ok I say its "uncached" but thats because I don't want this running a billion times per second and I think it might hitch with huge friends lists.
{
    {
        std::lock_guard<std::mutex> lock(friends_set_mutex);
        if (GetTickCount64() < next_update_friendslist_time || !(*(char*)OFF_s_runningUILevel)) // we will just not update the friends list in game because I really think this will hitch. STEAMAPI SUCKS
        {
            return friends_set.find(xuid) != friends_set.end();
        }
    }

    auto isteamfriends = *(__int64*)STEAMAPI_FRIENDS;
    auto fn_GetFriendCount = *(__int64*)(*(__int64*)isteamfriends + 0x18);
    int num_friends = ((int(__fastcall*)(__int64, int))fn_GetFriendCount)(isteamfriends, 4);

    // [LOCAL] collect into a local set first: the Steam calls below can block,
    // and they must not run while the mutex is held.
    std::unordered_set<__int64> rebuilt;

    // GetFriendByIndex must have been different in the api they used back then
    auto fn_GetFriendByIndex = *(__int64*)(*(__int64*)isteamfriends + 0x20);
    for (int i = 0; i < num_friends; i++)
    {
        __int64 out_friend = 0;
        ((void(__fastcall*)(__int64, __int64&, int, int))fn_GetFriendByIndex)(isteamfriends, out_friend, i, 4);
        if (out_friend)
        {
            rebuilt.insert(out_friend);
        }
    }

    bool result = false;
    {
        std::lock_guard<std::mutex> lock(friends_set_mutex);
        friends_set.swap(rebuilt); // [LOCAL] readers never see a half-built set
        next_update_friendslist_time = GetTickCount64() + 30 * 1000; // once every 30 seconds
        result = friends_set.find(xuid) != friends_set.end();
    }
    return result;
}

// [LOCAL] Steam answers two DIFFERENT questions on adjacent vtable slots:
//   slot 0x30 (index 6) = BIsSubscribedApp  -> "do you OWN it?"
//   slot 0x38 (index 7) = BIsDlcInstalled   -> "is it INSTALLED?"
// (Cross-check: the original author's note below says slot 0x18 = IsVACBanned,
//  and 0x18/8 = index 3 is exactly BIsVACBanned in ISteamApps - so the slot
//  mapping above is confirmed.)
// Both questions used to share ONE cache keyed only by itemid, so an
// "owns = true" answer poisoned the later "installed?" query: with the
// campaign DLC unchecked the campaign button still showed as enabled.
// Give each question its own cache.
std::unordered_map<INT32, bool> dlcContent;   // slot 0x30 - BIsSubscribedApp (owns)
std::unordered_map<INT32, bool> dlcInstalled; // slot 0x38 - BIsDlcInstalled  (installed?)

// [LOCAL] Steam's "installed?" answer is not trustworthy on its own: after a
// DLC is unchecked in Steam the licence state can still report installed
// while the mode's payload files are already gone - which is what kept the
// campaign button enabled.  Cross-check the real files in <game>\zone\.
// (Same approach as upstream Scroptss/T7Patch-src commit a0b1164.)
static bool IsModeContentFilePresent(INT32 appId)
{
    const wchar_t* contentFile = nullptr;
    switch (appId)
    {
    case 366840: contentFile = L"cp_common.xpak"; break; // campaign
    case 366841: contentFile = L"mp_common.xpak"; break; // multiplayer
    case 366842: contentFile = L"zm_common.xpak"; break; // zombies
    default: return true; // unknown id: no local payload to check
    }

    wchar_t executablePath[MAX_PATH]{};
    const auto pathLength = GetModuleFileNameW(nullptr, executablePath, MAX_PATH);
    if (pathLength == 0 || pathLength >= MAX_PATH)
    {
        return false;
    }

    std::error_code error;
    const auto path = std::filesystem::path(executablePath).parent_path() / L"zone" / contentFile;
    return std::filesystem::is_regular_file(path, error);
}
// [LOCAL] dlcContent is shared by GetOwnsContent/GetOwnsContent2, which can be
// called from different threads. operator[] inserts (and can rehash) on miss,
// so an unlocked find() racing it is undefined behaviour. The Steam round-trip
// stays outside the lock; only the cache lookup/update is serialized.
std::mutex dlc_content_mutex;
// BIsDlcInstalled
// 0x30 has similar signature and seems to be used the same way
// 0x18 isvacbanned
// 0xB0 GetDlcDownloadProgress

bool Protection::GetOwnsContent(INT64 _interface, INT32 itemid)
{
    // [LOCAL] Note: this used to arm the overlay ("the main menu must be
    // building its buttons").  Measured live, this query also runs on the
    // "press ENTER" screen, so the gate moved to MainThread and waits for the
    // Demonware sign-in instead.
    #if SPOOF_UNLOCK_ALL
        return IsModeContentFilePresent(itemid); // [LOCAL] spoof stays plausible too
    #endif

    // [LOCAL] previously: unlocked find() + operator[] write, racing other threads
    // [LOCAL] uses dlcInstalled: this slot (0x38) is BIsDlcInstalled, i.e. the
    // "is it installed?" question - sharing the "owns" cache here made the
    // campaign button appear enabled with the campaign DLC unchecked.
    {
        std::lock_guard<std::mutex> lock(dlc_content_mutex);
        auto it = dlcInstalled.find(itemid);
        if (it != dlcInstalled.end())
            return it->second;
    }

    const bool steamReportsInstalled = ((bool(__fastcall*)(INT64, INT64))GetOriginalSteamPtr(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_CHECK_OWNS_CONTENT))(_interface, itemid);
    // [LOCAL] Steam state alone is not enough: the mode's .xpak files must
    // really exist, otherwise a DLC unchecked in Steam still shows its button
    // as available.  Requires both answers to say "yes".
    const bool result = steamReportsInstalled && IsModeContentFilePresent(itemid);

    {
        std::lock_guard<std::mutex> lock(dlc_content_mutex);
        dlcInstalled[itemid] = result;
    }
    return result;
}

bool Protection::GetOwnsContent2(INT64 _interface, INT32 itemid)
{
    #if SPOOF_UNLOCK_ALL
        return IsModeContentFilePresent(itemid); // [LOCAL] spoof stays plausible too
    #endif

    // [LOCAL] previously: unlocked find() + operator[] write, racing other threads
    // This slot (0x30) is BIsSubscribedApp - the "do you OWN it?" question.
    {
        std::lock_guard<std::mutex> lock(dlc_content_mutex);
        auto it = dlcContent.find(itemid);
        if (it != dlcContent.end())
            return it->second;
    }

    const bool result = ((bool(__fastcall*)(INT64, INT64))GetOriginalSteamPtr(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_CHECK_OWNS_CONTENT2))(_interface, itemid);

    {
        std::lock_guard<std::mutex> lock(dlc_content_mutex);
        dlcContent[itemid] = result;
    }
    return result;
}

bool Protection::IsVacBanned(INT64 a)
{
    return false;
}

struct download_progress
{
    __int64 a;
    __int64 b;
    unsigned __int64 next;
};

std::unordered_map<INT32, download_progress> downloadProgress;
// [LOCAL] downloadProgress gets the same guard friends_set and the two DLC
// caches already have.  This slot is reached from whichever threads Steam
// drives the interface on, and every path used to touch the map twice
// unsynchronised - including operator[], whose insertion can rehash the whole
// table underneath a concurrent reader.
//
// The mutex is deliberately NOT held across the call into the real interface:
// that is an engine-side call, and holding a lock over one is the thing the
// rest of this file never does.
std::mutex downloadProgress_mutex;

void Protection::GetDlcDownloadProgress(INT64 a, INT32 b, INT64* c, INT64* d)
{
    const auto now = GetTickCount64();

    {
        std::lock_guard<std::mutex> lock(downloadProgress_mutex);

        auto it = downloadProgress.find(b);
        if (it == downloadProgress.end())
        {
            it = downloadProgress.emplace(b, download_progress()).first;
        }
        else if (now < it->second.next)
        {
            // Cached: hand back what the last real query returned.
            *c = it->second.a;
            *d = it->second.b;
            return;
        }

        it->second.next = now + (60 * 5 * 1000);
    }

    ((void(__fastcall*)(INT64, INT32, INT64*, INT64*))GetOriginalSteamPtr(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_GET_DLC_DOWNLOAD_PROGRESS))(a, b, c, d);

    {
        std::lock_guard<std::mutex> lock(downloadProgress_mutex);
        auto it = downloadProgress.find(b);
        if (it != downloadProgress.end())
        {
            it->second.a = *c;
            it->second.b = *d;
        }
    }
}

__int32 Protection::GetLobbyChatEntry(INT64 api, INT64 csteamidlobby, INT64 chatid, INT64 psteamuserid, INT64 pvdata, INT64 cubdata, INT64 chatentrytype)
{
    // pump the queue anyways
    auto result = ((int(__fastcall*)(INT64, INT64, INT64, INT64, INT64, INT64, INT64))GetOriginalSteamPtr(STEAMAPI_MATCHMAKING, STEAMAPI_MATCHMAKING_GETLOBBYCHATENTRY))(api, csteamidlobby, chatid, psteamuserid, pvdata, cubdata, chatentrytype);
    

    auto steamid = *(__int64*)psteamuserid;

    LobbyType sessionType = LobbyType::LOBBY_TYPE_AUTO;

    if (Protection::LobbySession_GetControllingLobbySession(LOBBY_MODULE_CLIENT))
    {
        sessionType = LOBBY_TYPE_GAME;
    }
    else
    {
        sessionType = LOBBY_TYPE_PRIVATE;
    }

    const auto session = Protection::LobbySession_GetSession(sessionType);
    bool found_xuid = false;

    for (int i = 0; i < 18; i++)
    {
        const auto client = Protection::LobbySession_GetClientByClientNum(session, i);
        if (client->activeClient && client->activeClient->fixedClientInfo.xuid == steamid)
        {
            found_xuid = true;
        }
    }

    if (!found_xuid)
    {
        return 0; // user isnt in our bo3 lobby and thus cannot chat with us
    }

    if (result > 0 && *(__int32*)(chatentrytype))
    {
        char* msg = (char*)pvdata;

        // [LOCAL] Bounded version of the original strlen() walk.
        //
        // The payload is a Steam length-delimited buffer, but strlen() assumed
        // a NUL terminator: a payload containing no NUL walked off the end of
        // the buffer until it happened to meet an unrelated zero byte, and the
        // two-byte lookahead at the final character read one past wherever it
        // stopped.  Note cubdata is the CAPACITY the caller handed Steam (the
        // byte count actually written is the return value), so it is a valid
        // upper bound but not the message length - bounding by it alone would
        // rewrite every byte up to the capacity instead of the message.
        //
        // So keep the original rule exactly - stop at the first NUL - and only
        // remove the overrun.  For every input the old code handled correctly
        // this picks the identical range; it differs only for the input that
        // used to read out of bounds.
        int msgCap = (int)cubdata;
        if (msgCap < 0)
            msgCap = 0;

        int msgLen = 0;
        while (msgLen < msgCap && msg[msgLen] != '\0')
            ++msgLen;

        for (int i = 0; i < msgLen; i++)
        {
            const bool hasNext = (i + 1) < msgLen;
            if (msg[i] == '^')
            {
                msg[i] = '.';
            }
            else if (msg[i] == '%')
            {
                msg[i] = '.';
            }
            else if (msg[i] == '$' && hasNext && msg[i + 1] == '(')
            {
                msg[i] = '.';
            }
            else if (msg[i] == '[' && hasNext && msg[i + 1] == '{')
            {
                msg[i] = '.';
            }
            else if (msg[i] < 0x20)
            {
                msg[i] = '.';
            }
            else if (msg[i] > 126)
            {
                msg[i] = '.';
            }
        }
    }

    return result;
}

__int64 Protection::CreateLobby(INT64 api, __int32 lobbyCreateType, __int32 maxplayers)
{
    return ((__int64(__fastcall*)(INT64, INT64, INT64))GetOriginalSteamPtr(STEAMAPI_MATCHMAKING, STEAMAPI_MATCHMAKING_CREATELOBBY))(api, 1, maxplayers);
}

const char* Protection::GetUsernameXUIDPtr(INT64 a, INT64 b)
{
    // [LOCAL] Only answer for our own XUID, and only when a custom name is
    // actually configured - otherwise fall through to the real Steam lookup.
    if (b == **(__int64**)s_playerData_ptr && CustomName[0])
    {
        return CustomName;
    }
    return ((char* (__fastcall*)(INT64, INT64))GetOriginalSteamPtr(STEAMAPI_STEAMUSER, STEAMAPI_STEAMUSER_VT_NAMEBYXUID))(a, b);
}

__int32 Protection::CL_SwitchState_Idle_Update(INT64 sw)
{
    if (strcmp(((const char* (__fastcall*)())REBASE(0x20EAD00))(), "CP"))
    {
        return 0;
    }
    return ((__int32(__fastcall*)(__int64))REBASE(0x131E350))(sw);
}

void Protection::SetNetworkPassword(__int64 pass)
{
    //XLOG("PASSWORD: %p", pass);
    Protection::PrivatePassword[0] = Protection::PrivatePassword[1];
    Protection::PrivatePassword[1] = pass;
    Protection::PrivatePassword[2] = GetTickCount64();
}

bool Protection::IsBadReadPtr(void* p)
{
    MEMORY_BASIC_INFORMATION mbi = { 0 };
    if (::VirtualQuery(p, &mbi, sizeof(mbi)))
    {
        DWORD mask = (PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY);
        bool b = !(mbi.Protect & mask);
        // check the page is not a guard page
        if (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) b = true;

        return b;
    }
    return true;
}

std::unordered_map<__int64, std::unordered_map<int, __int64>> Protection::SteamHAPIHooks;
void Protection::SwapSteamAPIPointer(__int64 hLibrary, int vPointerIndex, void* CallFuncReplace)
{
    auto steamLibrary = *(INT64*)hLibrary;
    auto OldProtection = 0ul;
    INT64* vtable = *(INT64**)steamLibrary;

    // [LOCAL] Remember the ORIGINAL vtable entry, and only ever remember it
    // once.  The old code stored whatever was in the slot on every call, which
    // poisoned the table on uninstall: Protect::uninstall() calls
    // SwapSteamAPIPointer(m, idx, GetOriginalSteamPtr(m, idx)) - the argument is
    // evaluated first, then the body stores *(vtable + idx), and at that moment
    // the slot already holds OUR thunk.  So the "original" recorded became the
    // hook itself, and a later install would have been handed our own thunk as
    // the function to call through -> infinite recursion.  Latent only because
    // Unload() currently runs once; first-swap-wins removes it for good.
    auto& slots = SteamHAPIHooks[hLibrary];
    if (slots.find(vPointerIndex) == slots.end())
    {
        slots[vPointerIndex] = *(vtable + vPointerIndex);
    }

    VirtualProtect(reinterpret_cast<void*>(vtable + vPointerIndex), 8, PAGE_EXECUTE_READWRITE, &OldProtection);
    *reinterpret_cast<void**>(vtable + vPointerIndex) = CallFuncReplace;
    VirtualProtect(reinterpret_cast<void*>(vtable + vPointerIndex), 8, OldProtection, &OldProtection);
}

INT64 Protection::GetOriginalSteamPtr(__int64 hLibrary, int vtIndex)
{
    if (SteamHAPIHooks.find(hLibrary) == SteamHAPIHooks.end())
    {
        return 0;
    }
    return SteamHAPIHooks[hLibrary][vtIndex];
}

bool fs_exists(const char* filename)
{
    // [LOCAL] GetFileAttributesA answers this on its own, and unlike
    // std::filesystem::exists() it cannot throw.  The exists() call that used
    // to sit first here was redundant AND dangerous: that overload raises
    // filesystem_error on any OS-level failure (a deny-ACL, an AV scanner
    // holding the file, the file disappearing between the two calls), and this
    // function runs from the MainThread's once-a-second poll with no handler
    // above it - the throw would leave the thread function and terminate the
    // game.  Behaviour is unchanged: the attribute call below already decided
    // every case the exists() test could return true for.
    const DWORD attr = GetFileAttributesA(filename);
    if (attr != INVALID_FILE_ATTRIBUTES)
    {
        return true;
    }
    // Any other error (access denied, a device path, a network hiccup) still
    // means "treat it as present", exactly as the old second branch did - a
    // config we cannot look at must not be mistaken for a first run.
    return GetLastError() != ERROR_FILE_NOT_FOUND;
}

// [LOCAL] THE config lock.  `user_config` is reached from three threads and
// every one of those paths used to run unsynchronised:
//   * MainThread     - polls the file's timestamp and, when it changed,
//                      reloads and pushes the settings into the engine;
//   * render thread  - DrawMenu() reads the settings to draw them and writes
//                      them back on every edit, then calls
//                      t7patch_config_save();
//   * WndProc thread - reads menu_key / menu_auto_open on every key message.
// What that cost, concretely: playername[16] could be read while loadfrom()
// was mid-strcpy (a torn name in the box); a reader could observe a
// HALF-APPLIED file (new playername next to the previous password) because
// loadfrom() published field by field; and networkpassword could be caught
// between free() and malloc(), handing strlen(NULL) to SetNetworkPassword.
//
// Two rules keep this cheap and deadlock-free, and they matter more than the
// lock itself:
//   1. It is NEVER held across an ENGINE call.  apply_settings() copies the
//      values out under the lock and only then calls SetPlayerName /
//      SetNetworkPassword - those are engine/Steam entry points that run
//      arbitrary code, and locking around them is how you get a deadlock.
//   2. It is never held across a file READ.  loadfrom() parses into a local
//      copy and takes the lock only to publish it, so the render thread's
//      per-frame reads are never stuck behind a disk read (the game folder can
//      sit behind an AV scanner).  Hold time there is a few hundred ns.
// The one piece of I/O the lock does cover is the ~1 KB write in saveto(),
// which is what serialises the writers.
std::mutex g_config_mutex;

struct patch_config
{
    // [LOCAL] One bit per key saveto() writes.  loadfrom() sets the bits it
    // actually found in the file, so "does this file mention every setting this
    // build knows about?" is a single mask comparison - see
    // load_settings_initial(), which rewrites a file that is missing any of
    // them.  Keep this list aligned with saveto()'s "outfile <<" lines: that is
    // the only other place a key is declared, and a setting added there without
    // a bit here would silently stop being detected as missing.
    enum : unsigned
    {
        K_PLAYERNAME = 1u << 0,
        K_ISFRIENDSONLY = 1u << 1,
        K_NETWORKPASSWORD = 1u << 2,
        K_BLOCK_D3DCOMPILER46 = 1u << 3,
        K_MENU_KEY = 1u << 4,
        K_MENU_AUTO_OPEN = 1u << 5,
        K_MENU_LANG = 1u << 6,
        K_TRANSLATE = 1u << 7,
        K_DEV_TOOLS = 1u << 8,
        K_SKIP_PVP = 1u << 9,
        K_SKIP_ZM = 1u << 10,
        K_ENGLISH_FALLBACK = 1u << 11,
        K_ALL = (1u << 12) - 1,
    };

    char playername[16];
    int isfriendsonly;
    // [LOCAL] A fixed inline buffer, not a heap pointer.  The old `char*` was
    // malloc'ed by the constructor and then free()/malloc()'ed by loadfrom()
    // and t7patch_cfg_set_network_password() - from different threads.  That
    // ownership dance is exactly what produced the NULL window (a reader
    // landing between free() and malloc()) and the "operator<< on a null
    // const char*" UB in saveto().  1023 bytes is the clamp every writer
    // already applied, so an inline array expresses every value the file can
    // hold and there is nothing left to own, free, or lose.  It also makes the
    // whole object trivially copyable, which is what capture/publish need.
    char networkpassword[1024];
    // [LOCAL] 1 = at launch, rename the game's legacy d3dcompiler_46.dll to
    // d3dcompiler_46.dll.bak so the engine cannot use it (see
    // t7patch_d3dcompiler46_reconcile).  Default OFF (opt-in): write
    // block_d3dcompiler46=1 into t7patch.conf, or tick the menu switch, to
    // enable it and restart the game.
    int block_d3dcompiler46;
    // [LOCAL] ImGui menu: hotkey virtual-key code (default VK_INSERT = 45) and
    // whether the menu opens automatically once the main menu is reached
    // (default ON - the owner's call; the ~1.5 s delay before it opens belongs
    // to overlay.cpp and is not a config value).
    int menu_key;
    int menu_auto_open;
    // [LOCAL] Overlay menu language: 1 = Chinese (default), 0 = English.
    int menu_lang;
    // [LOCAL] UI translation layer (src/translate.cpp): 1 = replace English UI
    // text with the dictionary in T7Patch\translate_zh.txt, 0 = off (default).
    // The second switch is the DEVELOPMENT TOOLS one: it turns on collection
    // mode, which records every distinct English UI string into
    // T7Patch\ui_dump.txt.  That file is the input for dictionary work AND for
    // the fragment-candidate pass (.codebuddy\ref\dev_pipeline.py), which reads
    // this same key out of t7patch.conf - one switch, both ends.  Deliberately
    // NOT in the overlay menu: it is a development tool, not a player setting.
    int translate;
    int dev_tools;
    // [LOCAL] Per-scene exceptions to 'translate' - both read as "this scene
    // stays untranslated", so the two switches in the menu are worded the same
    // way and a third scene would slot in without changing the shape.
    //
    // The defaults are the owner's call and they deliberately DIFFER: a
    // Multiplayer match is untranslated out of the box (the strings there are
    // player names, lobby names and workshop map names - nothing the dictionary
    // can say anything useful about, and the interface is shared with players
    // who do not read Chinese), while Zombies IS translated by default.  Both
    // are opt-out, and neither touches Campaign.
    //
    // Stored like any other setting.  The ENGINE-side meaning of "true" is
    // "do not translate right now" - see SetSceneBlocked in translate.cpp.
    int skip_pvp;
    int skip_zm;
    // [LOCAL] 1 = the garbled-text switch.  A workshop map can bring its OWN
    // font, and that font outranks the game's for every string the map draws -
    // with Latin glyphs only, every Chinese string draws as a row of boxes.
    // Stepping aside is not enough: that only restores text we translated
    // ourselves, while what the game and the map wrote is Chinese to begin
    // with.  So that text gets translated word by word instead.
    int english_fallback;
    // [LOCAL] Which of the keys above the last loadfrom() found in the file, and
    // K_ALL once saveto() has written it.  Starts at 0 ("nothing read yet"), so
    // a freshly constructed object - a first run with no file at all - is never
    // mistaken for a complete one.
    unsigned keys_seen;
    bool exists;
    std::filesystem::file_time_type modified;
    // [LOCAL] Set when the last loadfrom() found the file but could not OPEN
    // it.  Through keys_seen that case looks exactly like "written by an older
    // build" - both leave the mask short of K_ALL - and load_settings_initial()
    // answers the latter by rewriting the file, which after a failed READ would
    // replace whatever the player had with this build's defaults.  A property
    // of the last read rather than a setting, so it stays out of `values`.
    bool read_failed;

    // [LOCAL] A flat copy of everything a config file can carry.  loadfrom()
    // parses into one of these and publishes it in a single step, so a reader
    // sees either the old file or the new one - never a mix of the two.
    struct values
    {
        char playername[16];
        int isfriendsonly;
        char networkpassword[1024];
        int block_d3dcompiler46;
        int menu_key;
        int menu_auto_open;
        int menu_lang;
        int translate;
        int dev_tools;
        int skip_pvp;
        int skip_zm;
        int english_fallback;
        unsigned keys_seen;
    };

    patch_config()
    {
        memset(playername, 0, sizeof(playername));
        memset(networkpassword, 0, sizeof(networkpassword));
        isfriendsonly = true;
        // [LOCAL] Default OFF since 2026-09-16 (opt-in).  The rename makes the
        // engine fall back to the system copy of the shader compiler, and a
        // machine without a usable one can fail right there - so it ships off
        // and the player turns it on from the menu if they actually hit the
        // stutter it fixes.
        block_d3dcompiler46 = false;
        menu_key = 45;      // VK_INSERT
        menu_auto_open = 1; // auto-open on the main menu (user default)
        menu_lang = 1;      // Chinese by default
        translate = 0;      // translation off unless asked for
        dev_tools = 0;
        skip_pvp = 1;       // ...and a Multiplayer match is the one scene it stays off in
        skip_zm = 0;        // Zombies is translated like everything else
        english_fallback = 0; // replace normally; the garbled-text switch is opt-in
        keys_seen = 0;      // nothing read from a file yet
        exists = false;
        modified = std::filesystem::file_time_type();
        read_failed = false;
        // [LOCAL] Was: strcat_s(playername, "Unknown Soldier");
        // An empty playername now means "do not override the name the game
        // already has", so start with no custom name at all.  Set
        // playername=<name> in t7patch.conf to override it.
    }

    // ------------------------------------------------------------------
    //  Snapshot helpers.  Memory only - the caller holds g_config_mutex.
    // ------------------------------------------------------------------
    void capture_locked(values& v) const
    {
        memcpy(v.playername, playername, sizeof(v.playername));
        v.isfriendsonly = isfriendsonly;
        memcpy(v.networkpassword, networkpassword, sizeof(v.networkpassword));
        v.block_d3dcompiler46 = block_d3dcompiler46;
        v.menu_key = menu_key;
        v.menu_auto_open = menu_auto_open;
        v.menu_lang = menu_lang;
        v.translate = translate;
        v.dev_tools = dev_tools;
        v.skip_pvp = skip_pvp;
        v.skip_zm = skip_zm;
        v.english_fallback = english_fallback;
        v.keys_seen = keys_seen;
    }

    void publish_locked(const values& v)
    {
        memcpy(playername, v.playername, sizeof(playername));
        isfriendsonly = v.isfriendsonly;
        memcpy(networkpassword, v.networkpassword, sizeof(networkpassword));
        block_d3dcompiler46 = v.block_d3dcompiler46;
        menu_key = v.menu_key;
        menu_auto_open = v.menu_auto_open;
        menu_lang = v.menu_lang;
        translate = v.translate;
        dev_tools = v.dev_tools;
        skip_pvp = v.skip_pvp;
        skip_zm = v.skip_zm;
        english_fallback = v.english_fallback;
        keys_seen = v.keys_seen;
    }

    // [LOCAL] Assumes g_config_mutex is held: its two callers (saveto and
    // loadfrom) already own it, and std::mutex is deliberately NOT recursive.
    bool update_watcher_time_locked(const char* path)
    {
        bool did_exist_before = exists;
        if (!fs_exists(path))
        {
            exists = false;
            return did_exist_before != exists;
        }

        exists = true;

        // [LOCAL] error_code overload on purpose: the throwing one raises
        // filesystem_error on an OS-level failure, and this function is reached
        // from the MainThread's once-a-second poll (update_watcher_time) as
        // well as from saveto()/loadfrom(), with nothing above any of those to
        // catch it.  On an error the previous stamp is kept, so the tick
        // reports "unchanged" instead of reloading a config it cannot read.
        std::error_code ec;
        const std::filesystem::file_time_type time =
            std::filesystem::last_write_time(path, ec);
        if (ec)
        {
            return did_exist_before != exists;
        }

        bool was_same_time = modified == time;
        modified = time;

        return (did_exist_before != exists) || !was_same_time;
    }

    // [LOCAL] Locked wrapper for the MainThread's once-a-second poll, which
    // calls this on its own rather than through saveto()/loadfrom().
    bool update_watcher_time(const char* path)
    {
        std::lock_guard<std::mutex> lock(g_config_mutex);
        return update_watcher_time_locked(path);
    }

    // [LOCAL] Returns false when the file could not be opened for writing (a
    // read-only data directory, an AV scanner sitting on the file).  The caller
    // only uses the result to say so in the log - an unwritable config is not
    // fatal, the settings simply stay in memory for this session.
    bool saveto(const char* path)
    {
        // [LOCAL] Locked for the whole call, including the file write.  That is
        // what serialises the writers: in steady state only the render thread
        // saves (a menu Save), while the MainThread's single save is
        // load_settings_initial() at startup, which runs before CreateThread
        // starts the MainThread at all.  Holding the lock across a sub-1 KB
        // local write is cheap; what must never happen is holding it across an
        // engine call, and saveto() makes none.
        std::lock_guard<std::mutex> lock(g_config_mutex);

        // Copy the settings first: the file is then written from an immutable
        // snapshot, so a concurrent edit cannot produce a file that mixes two
        // different states (e.g. a new name with the old password).
        values v;
        capture_locked(v);

        std::ofstream outfile;
        outfile.open(path, std::ofstream::out | std::ofstream::binary);

        if (!outfile.is_open())
        {
            update_watcher_time_locked(path);
            return false;
        }

        // [LOCAL] Per-setting notes, each on the line(s) directly above its
        // setting.  Lines without '=' are skipped by loadfrom(), so comments
        // and blank lines are safe; keep '=' out of the prose itself.  The
        // project builds with /utf-8, so these literals are written as UTF-8.
        outfile << "# T7Patch 设置 - 保存后约 1 秒内生效，无需重启游戏" << std::endl;
        outfile << std::endl;

        outfile << "# 留空则使用游戏自带的名称" << std::endl;
        outfile << "playername=" << v.playername << std::endl;
        outfile << std::endl;

        outfile << "# 仅好友可以邀请/加入你（默认开）1/0开启关闭" << std::endl;
        outfile << "isfriendsonly=" << v.isfriendsonly << std::endl;
        outfile << std::endl;

        outfile << "# 私人房间密码；留空则不设置" << std::endl;
        // [LOCAL] No NULL test any more: networkpassword is an inline array, so
        // it is always a valid string.  The old "operator<< on a null const
        // char*" (undefined behaviour) is gone with the heap pointer itself.
        outfile << "networkpassword=" << v.networkpassword << std::endl;
        outfile << std::endl;

        outfile << "# 启动时把游戏目录的 d3dcompiler_46.dll 改名为 .bak，隔离旧版着色器编译器，需重启游戏生效（默认关）1/0开启关闭" << std::endl;
        outfile << "block_d3dcompiler46=" << v.block_d3dcompiler46 << std::endl;
        outfile << std::endl;

        outfile << "# 呼出菜单的按键（虚拟键码，45=Insert）" << std::endl;
        outfile << "menu_key=" << v.menu_key << std::endl;
        outfile << std::endl;

        outfile << "# 进入主菜单后自动打开菜单 1/0开启关闭" << std::endl;
        outfile << "menu_auto_open=" << v.menu_auto_open << std::endl;
        outfile << std::endl;

        outfile << "# 菜单语言 1/0中文英文" << std::endl;
        outfile << "menu_lang=" << v.menu_lang << std::endl;
        outfile << std::endl;

        outfile << "# UI 翻译：1/0开启关闭（把英文界面文本替换为 T7Patch\\translate_zh.txt 里的中文；游戏需为中文，简体/繁体均可。启动时若游戏语言不是中文，补丁会自动关掉它并把这一项改回 0）" << std::endl;
        outfile << "translate=" << v.translate << std::endl;
        outfile << std::endl;



        outfile << "# 修复文字异常 1/0开启关闭（默认关。用于兼容地图无中文字型导致的（口口口）显示异常）" << std::endl;
        outfile << "english_fallback=" << v.english_fallback << std::endl;
        outfile << std::endl;

        outfile << "# 关闭多人对局翻译 1/0开启关闭（默认开：多人对局不翻译；建立对局后生效，主菜单不受影响）" << std::endl;
        outfile << "skip_pvp=" << v.skip_pvp << std::endl;
        outfile << std::endl;

        outfile << "# 关闭僵尸对局翻译 1/0开启关闭（默认关：僵尸对局照常翻译；战役不受影响）" << std::endl;
        outfile << "skip_zm=" << v.skip_zm << std::endl;
        outfile << std::endl;

        outfile << "# 开发工具模式：采集界面英文文本 1/0开启关闭" << std::endl;
        outfile << "dev_tools=" << v.dev_tools << std::endl;
        outfile << std::endl;

        outfile.close();

        // [LOCAL] close() is where the buffer is flushed, and a failed flush
        // (a full disk, a write interrupted by another program) used to be
        // invisible: the truncated file was stamped as current, keys_seen was
        // raised to K_ALL and the caller was told "true".  Report it instead.
        // The timestamp is stamped first so the watcher does not immediately
        // reload the half-written file being left behind - the in-memory
        // settings stay authoritative for this session.
        if (!outfile)
        {
            update_watcher_time_locked(path);
            overlay::DebugLog("config file could not be written completely - "
                "the settings stay in memory for this session");
            return false;
        }

        // [LOCAL] The file on disk now carries every key this build knows, so
        // record that even though only a handful of bits may have been set when
        // it was read.  Without this a same-session check would see the stale
        // mask and rewrite the file again on every pass.
        keys_seen = K_ALL;
        update_watcher_time_locked(path);
        return true;
    }

    void loadfrom(const char* path)
    {
        // [LOCAL] Opened and parsed with the lock NOT held.  The render thread
        // reads config values on every frame, and a disk read here is the one
        // operation that can take an unbounded amount of time (a cold file, an
        // AV scanner sitting on it), so it must never happen underneath the
        // lock the menu needs to draw.
        std::ifstream infile;
        infile.open(path, std::ifstream::in | std::ifstream::binary);

        if (!infile.is_open())
        {
            std::lock_guard<std::mutex> lock(g_config_mutex);
            // [LOCAL] A read FAILURE, not an old format - see the note on
            // read_failed.  keys_seen stays short of K_ALL either way, and
            // this flag is the only thing that tells the two apart, so that
            // load_settings_initial() does not answer a locked file by
            // rewriting it with this build's defaults.
            read_failed = true;
            update_watcher_time_locked(path);
            return;
        }

        // A key the file does not mention keeps whatever is set right now, so
        // the parse starts from the live values - copied out under the lock,
        // then left alone until the finished copy is published.
        values v;
        {
            std::lock_guard<std::mutex> lock(g_config_mutex);
            capture_locked(v);
        }

        // [LOCAL] keys_seen is the one field that does NOT start from the live
        // copy above: every bit is cleared here and only the switch cases below
        // set one, so the finished value describes the FILE rather than the
        // running configuration.  load_settings_initial() compares it against
        // K_ALL to spot a config written by an older build, and rewrites that
        // file in the current format instead of leaving a half-populated one.
        v.keys_seen = 0;

        std::string line;
        // [LOCAL] Plain "while (getline(...))".  The old test was
        // "while (!std::getline(infile, line).eof())", which silently dropped
        // the LAST line of the file whenever it had no trailing newline:
        // getline reads that line and sets eofbit in the same call, so the loop
        // body never ran for it.  Appending "menu_auto_open=0" to the config by
        // hand therefore did nothing at all, while the file itself claims
        // settings apply within about a second.
        while (std::getline(infile, line))
        {
            // [LOCAL] Tolerate CRLF.  getline only strips '\n', so a file saved
            // by Notepad left a trailing '\r' glued to every value:
            // "playername=Bob" became "Bob\r", and - far worse -
            // networkpassword was hashed WITH the '\r', so the room password no
            // longer matched what the other player types and joining failed
            // with "the password is the same but it will not let me in".  The
            // patch's own writer emits LF, so this only ever bit hand edits.
            if (!line.empty() && line.back() == '\r')
                line.pop_back();

            auto sep = line.find("=");
            // [LOCAL] A line with no '=' is a comment or blank - skip it.  The
            // old extra test "sep >= (line.length() - 1)" also rejected a
            // PRESENT but EMPTY value ("playername="), so clearing a setting by
            // emptying it never took effect.  Unknown keys still fall through
            // the switch below, so a prose line that happens to contain '=' is
            // harmless.
            if (sep == std::string::npos)
            {
                continue;
            }

            // is this config resilliant to whitespace issues? nope!
            auto token = line.substr(0, sep);
            auto val = line.substr(sep + 1);
            switch (fnv1a(token.data()))
            {
            case FNV32("playername"):
            {
                v.keys_seen |= K_PLAYERNAME;
                if (val.length() > 15)
                {
                    val = val.substr(0, 15);
                }
                memset(v.playername, 0, sizeof(v.playername));
                strcpy_s(v.playername, sizeof(v.playername), val.data());
            }
            break;
            case FNV32("isfriendsonly"):
            {
                v.keys_seen |= K_ISFRIENDSONLY;
                std::istringstream ivalread(val);
                ivalread >> v.isfriendsonly;
                if (ivalread.fail())
                {
                    v.isfriendsonly = false; // its better to have it fail then to have people who cant disable this setting because of whatever reason
                }
            }
            break;
            case FNV32("networkpassword"):
            {
                v.keys_seen |= K_NETWORKPASSWORD;
                // [LOCAL] No malloc/free pair any more.  The old code freed the
                // shared pointer, set it to NULL and only then allocated the
                // replacement - a window in which another thread could read
                // NULL (and SetNetworkPassword's first act was strlen).  A
                // fixed inline buffer has no such window and needs no clamp:
                // _TRUNCATE stops at 1023 characters, which is the same limit
                // the old "val.substr(0, 1023)" applied.
                strncpy_s(v.networkpassword, sizeof(v.networkpassword), val.data(), _TRUNCATE);
            }
            break;
            case FNV32("block_d3dcompiler46"):
            {
                v.keys_seen |= K_BLOCK_D3DCOMPILER46;
                std::istringstream ivalread(val);
                ivalread >> v.block_d3dcompiler46;
                if (ivalread.fail())
                {
                    v.block_d3dcompiler46 = false; // default: disabled (opt-in)
                }
            }
            break;
            case FNV32("menu_key"):
            {
                v.keys_seen |= K_MENU_KEY;
                std::istringstream ivalread(val);
                ivalread >> v.menu_key;
                // [LOCAL] Same range check t7patch_cfg_set_menu_key() applies.
                // A value outside 1..255 can never come from a physical key, so
                // the hotkey would simply look broken with no obvious way back
                // other than editing the file again.
                if (ivalread.fail() || v.menu_key < 1 || v.menu_key > 255)
                {
                    v.menu_key = 45; // VK_INSERT
                }
            }
            break;
            case FNV32("menu_auto_open"):
            {
                v.keys_seen |= K_MENU_AUTO_OPEN;
                std::istringstream ivalread(val);
                ivalread >> v.menu_auto_open;
                if (ivalread.fail())
                {
                    v.menu_auto_open = 1; // default: auto-open (user default)
                }
            }
            break;
            case FNV32("menu_lang"):
            {
                v.keys_seen |= K_MENU_LANG;
                std::istringstream ivalread(val);
                ivalread >> v.menu_lang;
                if (ivalread.fail())
                {
                    v.menu_lang = 1; // default: Chinese
                }
            }
            break;
            case FNV32("translate"):
            {
                v.keys_seen |= K_TRANSLATE;
                std::istringstream ivalread(val);
                ivalread >> v.translate;
                if (ivalread.fail())
                {
                    v.translate = 0; // default: off
                }
            }
            break;
            case FNV32("dev_tools"):
            {
                v.keys_seen |= K_DEV_TOOLS;
                std::istringstream ivalread(val);
                ivalread >> v.dev_tools;
                if (ivalread.fail())
                {
                    v.dev_tools = 0; // default: off
                }
            }
            break;
            // [LOCAL] The same switch under its pre-2026-09-18 name.  It is read
            // - so an existing t7patch.conf keeps collecting instead of going
            // quiet - but it deliberately does NOT raise K_DEV_TOOLS: leaving
            // keys_seen short of K_ALL is what makes load_settings_initial()
            // rewrite the file once, migrating the value onto the new key name.
            case FNV32("dump_ui_strings"):
            {
                std::istringstream ivalread(val);
                ivalread >> v.dev_tools;
                if (ivalread.fail())
                {
                    v.dev_tools = 0; // default: off
                }
                // Deliberately no log line from here: this parser IS the config
                // layer, and the rewrite that carries the migration is already
                // reported by load_settings_initial() ("config file was in an
                // older format (...) - rewritten in the current format").  The
                // other half of the evidence is the file itself: after one run
                // it reads dev_tools=1 and no longer mentions the old name.
            }
            break;
            case FNV32("skip_pvp"):
            {
                v.keys_seen |= K_SKIP_PVP;
                std::istringstream ivalread(val);
                ivalread >> v.skip_pvp;
                if (ivalread.fail())
                {
                    v.skip_pvp = 1; // default: a match stays untranslated
                }
            }
            break;

            case FNV32("english_fallback"):
            {
                v.keys_seen |= K_ENGLISH_FALLBACK;
                std::istringstream ivalread(val);
                ivalread >> v.english_fallback;
                if (ivalread.fail())
                {
                    v.english_fallback = 0; // default: replace normally
                }
            }
            break;

            case FNV32("skip_zm"):
            {
                v.keys_seen |= K_SKIP_ZM;
                std::istringstream ivalread(val);
                ivalread >> v.skip_zm;
                if (ivalread.fail())
                {
                    v.skip_zm = 0; // default: Zombies is translated
                }
            }
            break;
            }
        }

        infile.close();

        // [LOCAL] Publish the whole parsed file in one step.  Publishing field
        // by field (the old behaviour, because loadfrom wrote straight into the
        // shared object) let a reader see a config that never existed on disk -
        // new playername next to the previous password.
        std::lock_guard<std::mutex> lock(g_config_mutex);
        publish_locked(v);
        read_failed = false; // the file was opened and parsed after all
        update_watcher_time_locked(path);
    }
};

patch_config user_config;

void apply_settings(); // [LOCAL] forward declaration: defined below this block

// [LOCAL] "An in-process Save still owes the engine a push."  Set by
// t7patch_config_save() on the render thread (the menu's Save buttons) and
// consumed by MainThread, which is where apply_settings() is allowed to run.
//
// Why the file watcher cannot do this job: saveto() records the timestamp of
// the file it just wrote, so the next poll compares equal and reports
// "unchanged" - correctly, because the only thing a file watcher knows is the
// file.  So a menu Save wrote the file and the in-memory config and then
// stopped there: playername / networkpassword / isfriendsonly reached the
// engine only on the next game start.  Measured 2026-09-15 11:37:35 - the log
// carries "config written to disk" and no "playername applied to the
// front-end strings" after it, while the conf on disk did hold
// playername=muyou233; that is the "I have to restart to rename myself" the
// user reported.
//
// The flag carries no data on purpose: the setters have already updated
// user_config, MainThread only owes the engine call.  External edits still come
// in through the watcher, so both sources are covered.
std::atomic<bool> g_config_apply_pending{ false };

// [LOCAL] Config helpers exposed to dllmain.cpp / Hooks.cpp.  The 46 block is
// installed long before apply_settings() runs, so it needs its own read-only
// config load (no engine calls - safe this early) plus a simple getter.
void t7patch_load_config_early()
{
    if (fs_exists(PATCH_CONFIG_LOCATION))
    {
        user_config.loadfrom(PATCH_CONFIG_LOCATION);
    }
}

bool t7patch_block_d3dcompiler46_enabled()
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.block_d3dcompiler46 != 0;
}

int t7patch_menu_key()
{
    // [LOCAL] Read from the WndProc thread on every key message, and from the
    // render thread while it draws the hotkey row - hence the lock.
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.menu_key;
}

// [LOCAL] Overlay menu language (1 = Chinese, 0 = English).
int t7patch_cfg_menu_lang()
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.menu_lang;
}

void t7patch_cfg_set_menu_lang(int value)
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.menu_lang = value ? 1 : 0;
}

// [LOCAL] UI translation layer switches (see src/translate.cpp).
// [LOCAL] Language gate latch (2026-09-16).  translate::Init() sets it when the
// game itself is not running Chinese, and it masks the mod-translation
// switch OFF.  The stored value is written off separately by
// load_settings_initial() below - see the note there for why it owns the write.
//
// Why the latch lives here rather than in translate.cpp: the FIRST Init of a
// session runs from RunPatching() (dllmain.cpp), and load_settings_initial()
// re-reads the conf a few ms later - which puts translate=1 straight back into
// user_config.  Editing the config value from the gate was therefore silently
// undone (measured 2026-09-16 12:57:36: the gate logged "switched off" and 3 ms
// later the dictionary loaded anyway, 860 entries).  A separate latch cannot be
// overwritten by a loadfrom(), which is exactly what makes the gate stick.
std::atomic<bool> g_translate_language_block{ false };

// [LOCAL] "The gate read a language it is sure about, and that language is not
// Chinese" - i.e. the switch-off is meant to outlive this session.
// Set from translate.cpp right next to the latch, consumed by
// load_settings_initial(), which owns the write to the conf file.
//
// Kept separate from the latch on purpose: the latch also fires for a language
// that could not be read at all (fail closed - see translate.cpp), and that case
// must NOT rewrite the player's file on a guess.  Only a language we actually
// read is persisted.
std::atomic<bool> g_translate_persist_request{ false };

void t7patch_cfg_block_translate(int blocked)
{
    g_translate_language_block.store(blocked != 0);
}

void t7patch_cfg_persist_translate_off()
{
    g_translate_persist_request.store(true);
}

bool t7patch_cfg_translate_enabled()
{
    // The masked answer is the EFFECTIVE state: it is what Init acts on and what
    // the menu draws, so the switch can never read ON while the layer is held
    // off.  The stored value is deliberately left alone (see above).
    std::lock_guard<std::mutex> lock(g_config_mutex);
    if (user_config.translate == 0)
        return false;
    // [LOCAL] The start-up language gate exists because every replacement in the
    // Chinese dictionary needs CJK glyphs that a non-Chinese language pack does
    // not ship - on such a game it could only paint boxes.  The garbled-text
    // switch is plain ASCII and renders on any pack, so the gate must NOT block
    // it: otherwise the very case it exists for (an English game, a map whose
    // own font has no Chinese glyphs) could never be switched on.
    if (user_config.english_fallback != 0)
        return true;
    return !g_translate_language_block.load();
}

bool t7patch_cfg_dev_tools()
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.dev_tools != 0;
}

// [LOCAL] Per-scene exceptions to the translation layer - see framework.h.
// "true" reads as "this scene stays untranslated".  They are read by the
// MainThread, which turns them plus the measured scene into
// translate::SetSceneBlocked().  Two near-identical pairs on purpose: the menu
// draws them as two independent switches, and a combined value would lose which
// one the player ticked.
bool t7patch_cfg_skip_pvp()
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.skip_pvp != 0;
}

void t7patch_cfg_set_skip_pvp(int skip)
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.skip_pvp = skip ? 1 : 0;
}

bool t7patch_cfg_skip_zm()
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.skip_zm != 0;
}

void t7patch_cfg_set_skip_zm(int skip)
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.skip_zm = skip ? 1 : 0;
}

// [LOCAL] 2026-09-19: leave the current map's text alone (see framework.h).
// Nothing here reloads a dictionary - the flag is read straight off the
// config by the translate layer, so flipping it takes effect on the next
// string the game draws.
bool t7patch_cfg_english_fallback()
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.english_fallback != 0;
}

void t7patch_cfg_set_english_fallback(int on)
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.english_fallback = on ? 1 : 0;
}

// [LOCAL] Toggle the translation layer from the menu (page 2, next to the
// dictionary update button).  Writing the value is all the menu does; making it
// take effect is the config-apply path, which re-runs translate::Init().
void t7patch_cfg_set_translate(int enabled)
{
    // [LOCAL] Only the menu turns this ON, and doing so is the player overriding
    // the start-up language gate: release the latch, so the switch means what it
    // says from that moment on for the rest of the session.
    if (enabled)
        g_translate_language_block.store(false);

    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.translate = enabled ? 1 : 0;
}

// [LOCAL] Change the overlay hotkey (virtual-key code) from the menu.
void t7patch_cfg_set_menu_key(int vk)
{
    if (vk <= 0 || vk >= 256)
        return;
    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.menu_key = vk;
}

bool t7patch_menu_auto_open()
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.menu_auto_open != 0;
}

// [LOCAL] Toggle auto-open from the overlay menu.
void t7patch_cfg_set_menu_auto_open(bool v)
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.menu_auto_open = v ? 1 : 0;
}

// [LOCAL] Called by the overlay menu: flips the 46 switch in memory.
void t7patch_config_set_block46(bool enable)
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.block_d3dcompiler46 = enable ? 1 : 0;
}

// [LOCAL] ============================================================
//  Legacy shader-compiler opt-out - the FILE layer.
//
//  Same feature the toggle has always described.  "Block the legacy shader
//  compiler" shipped in 3.07 and - as of 2026-09-15 - had never actually been
//  exercised end to end, so the work below is its first real test, not a new
//  mechanism.  What that first test showed: the original LoadLibraryExW hook,
//  which answered "not found" for d3dcompiler_46.dll, logged itself armed and
//  never once fired across four measured sessions, the module never appeared
//  in the process, and the file's last-access time never moved - it was
//  answering a question the game never asked.  The one fact this feature was
//  built on is "with the file gone, the game behaves", and a rename changes
//  exactly that fact: it is visible to every API, to directory enumeration
//  and to other processes (Steam, the driver), none of which a hook can cover.
//
//  switch on  -> <game>\d3dcompiler_46.dll     -> <game>\d3dcompiler_46.dll.bak
//  switch off -> <game>\d3dcompiler_46.dll.bak -> <game>\d3dcompiler_46.dll
//
//  The parked copy keeps the ".bak" suffix and stays next to BlackOps3.exe.
//  That is deliberate: the loader only ever asks for the exact name
//  "d3dcompiler_46.dll", so a suffixed file is as invisible to the engine as
//  a moved one, and someone who uninstalls the patch by deleting d3d11.dll
//  finds the original right where it belongs instead of having to know about
//  T7Patch\.  Nothing accumulates either: the destination name is a constant
//  and the move replaces whatever is already there (see hide_file below), so
//  a Steam integrity check that re-downloads the file simply means the next
//  launch overwrites the parked copy with the fresh one.
//
//  The state follows the switch, not the session.  It is re-applied at every
//  launch (before the engine can look at the file, see dllmain.cpp), so a
//  hard kill - or a Steam integrity check that brought the file back -
//  heals itself on the next run.
//
//  One rule governs both directions: the .dll in the game folder is the
//  authoritative copy.  Hiding replaces the parked file with it, and
//  restoring refuses to overwrite it - a re-downloaded .dll may be newer
//  than the copy we parked, so the patch never writes over it.
// ============================================================

namespace
{
    // Both candidate paths, built from the MAIN MODULE location.  Same
    // reasoning as t7log::BuildPaths: the process working directory is not
    // necessarily the game folder, so a relative path could move a file
    // somewhere else entirely.  The last separator is found by hand to keep
    // this free of extra CRT headers.
    bool d3dc46_build_paths(wchar_t* dllOut, size_t dllCap, wchar_t* bakOut, size_t bakCap)
    {
        wchar_t exe[MAX_PATH] = {};
        const DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
        if (n == 0 || n >= MAX_PATH)
            return false;

        size_t cut = 0;
        for (size_t i = 0; i < n; ++i)
        {
            if (exe[i] == L'\\' || exe[i] == L'/')
                cut = i;
        }
        if (cut == 0)
            return false;
        exe[cut] = L'\0';

        if (swprintf_s(dllOut, dllCap, L"%s\\d3dcompiler_46.dll", exe) < 0)
            return false;
        return swprintf_s(bakOut, bakCap, L"%s\\d3dcompiler_46.dll.bak", exe) >= 0;
    }

    const char* d3dc46_state_name(int state)
    {
        switch (state)
        {
        case 0:  return "visible";
        case 1:  return "hidden";
        case 3:  return "both copies present";
        default: return "file not found";
        }
    }
}

// 0 = d3dcompiler_46.dll sits in the game folder, 1 = only the .bak is there,
// 2 = neither copy exists, 3 = both.  Reads the DISK, never the config: the
// menu must be able to show that the rename failed instead of echoing the
// value we asked for.
int t7patch_d3dcompiler46_file_state()
{
    wchar_t dll[MAX_PATH] = {};
    wchar_t bak[MAX_PATH] = {};
    if (!d3dc46_build_paths(dll, MAX_PATH, bak, MAX_PATH))
        return 2;

    const bool hasDll = GetFileAttributesW(dll) != INVALID_FILE_ATTRIBUTES;
    const bool hasBak = GetFileAttributesW(bak) != INVALID_FILE_ATTRIBUTES;
    if (hasDll && hasBak)
        return 3;
    if (hasDll)
        return 0;
    if (hasBak)
        return 1;
    return 2;
}

// Applies the wanted on-disk state; true when the disk matches the request
// afterwards.  Every failure is logged with its Win32 error - a read-only
// game folder (Program Files without elevation) is the realistic one, and the
// switch must not pretend it worked when it did not.
bool t7patch_d3dcompiler46_hide_file(bool hide)
{
    wchar_t dll[MAX_PATH] = {};
    wchar_t bak[MAX_PATH] = {};
    if (!d3dc46_build_paths(dll, MAX_PATH, bak, MAX_PATH))
    {
        t7log::Append("block", "46 file: cannot resolve the game folder");
        return false;
    }

    const bool hasDll = GetFileAttributesW(dll) != INVALID_FILE_ATTRIBUTES;
    const bool hasBak = GetFileAttributesW(bak) != INVALID_FILE_ATTRIBUTES;

    if (hide)
    {
        if (!hasDll)
        {
            // Already hidden (an earlier session) or genuinely absent (a
            // Steam "verify" that removed it).  Nothing to hide either way,
            // and the requested state is satisfied.
            return true;
        }

        // A .bak that is still there means the file came back - in practice a
        // Steam integrity check re-downloading it.  The destination name is a
        // constant, so the game folder never accumulates copies: there is
        // exactly one .bak and it always holds the newest downloaded .dll.
        if (hasBak)
            t7log::Append("block", "46 file: stale parked copy found - replacing it");

        // MOVEFILE_REPLACE_EXISTING is what makes the sentence above true: the
        // destination is deleted and the source takes its place, in one call.
        // Without it the second launch of this scenario would fail with
        // ERROR_ALREADY_EXISTS and leave the .dll sitting in the game folder,
        // where the engine can see it.  The .dll in the game folder is always
        // the authoritative copy.
        if (!MoveFileExW(dll, bak, MOVEFILE_REPLACE_EXISTING))
        {
            char msg[160] = {};
            snprintf(msg, sizeof(msg), "46 file: hide FAILED err=%lu",
                (unsigned long)GetLastError());
            t7log::Append("block", msg);
            return false;
        }
        t7log::Append("block", "46 file: hidden (renamed to d3dcompiler_46.dll.bak)");
        return true;
    }

    if (!hasBak)
        return true; // nothing of ours to put back

    //  A .dll sitting next to our .bak is the AUTHORITATIVE copy - in practice
    //  a Steam update or integrity check that re-downloaded the file while it
    //  was parked, and that download can be a NEWER build than the one we
    //  kept.  The hide path below already calls the game-folder .dll
    //  authoritative; the restore path must agree, or it would silently
    //  downgrade a game file by moving the older .bak over it.  Keep the .dll
    //  and drop our own leftover instead.  (Only reachable with the switch
    //  OFF and both copies on disk: a verify during play, then switching this
    //  off before the next launch.)
    if (hasDll)
    {
        if (!DeleteFileW(bak))
        {
            char msg[160] = {};
            snprintf(msg, sizeof(msg), "46 file: stale .bak not removed err=%lu",
                (unsigned long)GetLastError());
            t7log::Append("block", msg);
            return true; // the requested state (file usable in the game folder) holds
        }
        t7log::Append("block",
            "46 file: kept the game folder .dll as authoritative, removed our stale .bak");
        return true;
    }

    if (!MoveFileExW(bak, dll, MOVEFILE_REPLACE_EXISTING))
    {
        char msg[160] = {};
        snprintf(msg, sizeof(msg), "46 file: restore FAILED err=%lu",
            (unsigned long)GetLastError());
        t7log::Append("block", msg);
        return false;
    }
    t7log::Append("block", "46 file: restored (d3dcompiler_46.dll.bak renamed back to .dll)");
    return true;
}

// Startup reconciliation, called from the DllMain-era thread (dllmain.cpp)
// long before the renderer initialises.  Always logs one line carrying the
// REAL state, so "did the switch do anything?" is answerable from the log.
void t7patch_d3dcompiler46_reconcile()
{
    const bool wantHidden = t7patch_block_d3dcompiler46_enabled();
    const bool applied = t7patch_d3dcompiler46_hide_file(wantHidden);

    char msg[192] = {};
    snprintf(msg, sizeof(msg), "46 file: startup %s (switch=%s)%s",
        d3dc46_state_name(t7patch_d3dcompiler46_file_state()),
        wantHidden ? "hide" : "show",
        applied ? "" : "  -- REQUESTED STATE NOT APPLIED");
    t7log::Append("block", msg);
}

// [LOCAL] Persist the current config to disk AND apply the live settings, so
// menu edits (playername, friends-only, ...) take effect immediately.
void t7patch_config_save()
{
    // [LOCAL] Persist here, apply on MainThread.  Still no apply_settings() on
    // this thread: this runs from the overlay menu, i.e. from the render
    // thread, and apply_settings touches engine state (window text, Steam,
    // dvars) that is only safe from the update thread.
    //
    // The hand-off is the explicit flag below, NOT the file watcher - the
    // watcher cannot fire for a menu Save (saveto() stamps the timestamp it
    // just wrote, so the next poll legitimately reports "unchanged").  That
    // missing hand-off is why a menu rename needed a restart until now; see the
    // note on g_config_apply_pending.  MainThread picks the flag up on its next
    // 1 s tick, which is the "applies within ~1 s" the config template
    // promises.
    const bool written = user_config.saveto(PATCH_CONFIG_LOCATION);
    g_config_apply_pending = true;

    // [LOCAL] One line per write, so "I pressed Save and nothing happened" can
    // be settled from the log: this line means the file was written, and its
    // absence means the click never reached the handler.  Saves are
    // click-driven, so this cannot flood the log.
    //
    // [LOCAL] The result is now reported rather than assumed.  saveto() also
    // fails when the flush came up short (see the note there), and claiming
    // "written to disk" right after that failure is the kind of log line that
    // sends a bug hunt in the wrong direction.  The apply hand-off still
    // happens either way - the settings are live for this session regardless.
    overlay::DebugLog(written ? "config written to disk"
                              : "config could not be written to disk");
}

// [LOCAL] Field-level accessors for the overlay menu (patch_config lives in
// this file, so the menu talks to it through these narrow helpers).
//
// The two string getters COPY into the caller's buffer instead of handing back
// a pointer into the shared object.  Returning `const char*` and letting the
// caller copy afterwards would have left the last hole open: the lock would be
// released before the copy, so the caller could still read a buffer that
// loadfrom() was rewriting underneath it.
void t7patch_cfg_playername(char* dst, size_t dstSize)
{
    if (!dst || dstSize == 0)
        return;
    std::lock_guard<std::mutex> lock(g_config_mutex);
    strncpy_s(dst, dstSize, user_config.playername, _TRUNCATE);
}

// [LOCAL] The game's own current player name.  While no custom name is set the
// engine keeps it in pNameBuffer (SetPlayerName only overwrites that buffer
// for a real custom name), so reading it shows the user what the game is
// actually using.  Copied into a static because the caller only keeps the
// pointer for the duration of the menu refresh.
//
// This is game state, not config state, so g_config_mutex does not apply.  It
// needs no lock of its own either: only the render thread calls it, and the one
// writer of pNameBuffer inside this DLL - SetPlayerName() on the MainThread -
// writes it only for a NON-empty custom name, which is exactly the case where
// the caller does not consult this fallback.
const char* t7patch_game_playername()
{
    static char nameBuf[24] = {};
    const char* src = (const char*)pNameBuffer;
    if (src && *src)
    {
        strncpy_s(nameBuf, sizeof(nameBuf), src, _TRUNCATE);
        return nameBuf;
    }
    return "";
}

void t7patch_cfg_set_playername(const char* v)
{
    if (!v)
        return; // strncpy_s with a null source trips the invalid-parameter handler
    std::lock_guard<std::mutex> lock(g_config_mutex);
    strncpy_s(user_config.playername, sizeof(user_config.playername), v, _TRUNCATE);
}

bool t7patch_cfg_friends_only()
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    return user_config.isfriendsonly != 0;
}

void t7patch_cfg_set_friends_only(bool v)
{
    std::lock_guard<std::mutex> lock(g_config_mutex);
    user_config.isfriendsonly = v ? 1 : 0;
}

void t7patch_cfg_network_password(char* dst, size_t dstSize)
{
    if (!dst || dstSize == 0)
        return;
    std::lock_guard<std::mutex> lock(g_config_mutex);
    strncpy_s(dst, dstSize, user_config.networkpassword, _TRUNCATE);
}

void t7patch_cfg_set_network_password(const char* v)
{
    if (!v)
        v = "";

    // [LOCAL] A plain copy into the fixed buffer.  The old version malloc'ed a
    // replacement, swapped the pointer and freed the previous buffer, with a
    // hand-rolled memcpy to dodge strcpy_s's ERANGE on over-long input - all of
    // which existed only because the value was heap-allocated.  _TRUNCATE now
    // enforces the same 1023-character limit with none of that machinery.
    std::lock_guard<std::mutex> lock(g_config_mutex);
    strncpy_s(user_config.networkpassword, sizeof(user_config.networkpassword), v, _TRUNCATE);
}

void apply_settings()
{
    // [LOCAL] Copy the settings out under the lock, then call the engine with
    // the copies.  Holding g_config_mutex across SetPlayerName / SetFriendsOnly
    // / SetNetworkPassword would be the one genuinely dangerous thing this lock
    // could do: those are engine and Steam entry points that run arbitrary code
    // - including callbacks that read the config back - and the mutex is not
    // recursive.
    char playername[16];
    char networkpassword[1024];
    bool isfriendsonly;
    {
        std::lock_guard<std::mutex> lock(g_config_mutex);
        memcpy(playername, user_config.playername, sizeof(playername));
        memcpy(networkpassword, user_config.networkpassword, sizeof(networkpassword));
        isfriendsonly = user_config.isfriendsonly != 0;
    }

    SetPlayerName(playername);
    SetFriendsOnly(isfriendsonly);
    SetNetworkPassword(networkpassword);

    // [LOCAL] One line per push, so the log answers "did my Save reach the
    // engine?" without guessing.  For a menu Save it follows "config written to
    // disk"; for a hand-edited conf it appears on its own.  Both lines used to
    // be missing in the same way, and telling them apart is exactly what the
    // 2026-09-15 rename investigation needed.
    overlay::DebugLog("settings applied to the engine");

    // [LOCAL] Give the translation layer a retry on every config (re-)apply:
    // at start-up RunPatching may run before the config is readable, and a user
    // who flips translate=1 by hand should not have to restart the game.
    // Init, NOT EnsureLoaded: Init re-reads the config, so turning the switch
    // OFF from the menu takes effect too - EnsureLoaded returned early while
    // the layer was still enabled and would leave it running.  Init itself
    // short-circuits a re-apply that changes nothing, so a menu Save no longer
    // re-parses the dictionary or re-logs the init line.
    translate::Init();
}

DWORD WINAPI MainThread(LPVOID lpParam)
{
    std::srand((unsigned int)time(NULL)); // [LOCAL] C4244: explicit time_t truncation
    *(__int32*)OFFSET(0x11250898) = rand();

    // [LOCAL] Overlay gate.  Eight candidate signals were measured live on
    // 2026-09-14.  Seven of them failed to separate the "press ENTER" screen
    // from the real main menu:
    //   s_runningUILevel      - 0->1 already on the "press ENTER" screen
    //   DLC ownership query   - fires before connecting
    //   Demonware sign-in     - completes in the background on that screen
    //   DW_LOBBY              - gets its value at the same instant (UI 0->1)
    //   PTR_LobbyVM           - still 0x12 on that screen, real pointer ~1 min later
    //   s_playerData_ptr      - valid before UI 0->1
    //   uistate[-8..+15]      - a 24-byte neighbourhood dump: only the byte of
    //                           s_runningUILevel itself ever changes, the rest
    //                           stays zero, so nothing there distinguishes them
    //
    // What finally worked is a real screen signal, found by watching the UI text
    // the game resolves: the MAIN MENU's own labels (Campaign / Multiplayer /
    // Zombies buttons, quick-join bar) are built at render time and appear only
    // when that screen is up - the title screen resolves just "按ENTER开始" and
    // the connecting screen "正在连接到在线服务器".  Hooks.cpp turns that into
    // hooks::UiMainMenuSeen(), and the user's title-screen dismissal stays a
    // precondition (so a pre-resolved label cannot arm early).
    //
    // There is deliberately NO timer fallback any more (removed 2026-09-15, on
    // the user's call: "不要兜底吧，只保留在主菜单自动弹出").  The gate is that
    // one screen signal plus the dismissal precondition - nothing else can open
    // the menu.
    //
    // Why the timer had to go: measured on 2026-09-15 (log session 10:45:08) the
    // gate opened at 10:46:26.603, exactly 60 s after "front-end UI level = 1"
    // (10:45:26.555), with neither a "title screen dismissed" nor a
    // "main-menu label rendered" line in between.  The uptime fallback had fired
    // while the user was simply idling on the "按ENTER开始" screen - the very
    // screen this gate exists to keep out - and popped the overlay over it a
    // minute after the front-end came up.  Re-basing the timer on the dismissal
    // (the first fix attempt) would have removed that specific symptom, but any
    // timer still means "the menu can open by itself somewhere I did not ask
    // for", so it is gone for good rather than tuned.
    //
    // The trade-off, stated plainly: if hooks::UiMainMenuSeen() never goes true
    // (an unlisted localisation, or a front-end flow that resolves none of the
    // marker labels), the overlay cannot be opened at all.  That is visible in
    // the log as "gate opened" never appearing - if it ever happens, the marker
    // list in Hooks.cpp IsMainMenuLabel() is what to extend.

    int lastUiLevel = -1;
    bool lastSignedIn = false;

    // [LOCAL] s_runningUILevel is 0 in two very different situations: before the
    // front-end exists at all, and for the WHOLE time a match is being played.
    // The first one is why the engine calls in this loop are held back at all;
    // the second one is why the scene gate must NOT be held back with them.
    // Measured 2026-09-16: with the gate tied to the current level it froze for
    // the entire match, so flipping either switch in the menu - or hand-editing
    // t7patch.conf - only took effect after walking back out to the lobby.  That
    // is what "I ticked 关闭僵尸翻译 and Zombies was still translated" was.
    // One latch separates the two situations: once the level has been non-zero,
    // the engine UI is up for good (it does not un-boot mid-session).
    bool uiEverUp = false;

    // [LOCAL] Scene gate edge detection - see the block inside the loop.
    // lastSceneMode is the session mode the last log line saw, so the log prints
    // once per SCENE change (into a match, back out, into Zombies) instead of
    // once per tick.  It is also the diagnostic that answers "which mode code
    // does Zombies report?", which is what decides whether the two letter codes
    // single the two modes out at all.
    bool lastSceneBlocked = false;
    char lastSceneMode[16] = {};

    // [LOCAL] NOTE: do NOT call Live_SystemInfo() with arbitrary infoTypes to
    // probe the connection state.  Tried on 2026-09-14 and it hard-crashes the
    // game at the front-end transition: the function walks a table of info
    // entries and dereferences a NULL string for the infoTypes it does not
    // implement (AV at blackops3.exe+0x227CAC4, i.e. the I_stricmp area,
    // Rcx=0, reached from the Live code).  Probing game internals with values
    // the game itself never passes is not worth the risk.

    for (;;)
    {
        arxan_bypass::maintain();

        // [LOCAL] Two ways a config reaches us, and at most one apply per tick:
        //   * the file changed under us - a hand-edited t7patch.conf, or another
        //     process writing it: reload it, then push to the engine;
        //   * an in-process Save owes the engine a push (menu Save buttons) -
        //     user_config already holds the new values, only the engine call is
        //     missing.  The watcher structurally cannot see this one; see the
        //     note on g_config_apply_pending.
        // The flag is exchanged unconditionally rather than ||-ed away, so a
        // tick that legitimately sees both sources still clears it.
        const bool fileChanged = user_config.update_watcher_time(PATCH_CONFIG_LOCATION);
        if (fileChanged)
            user_config.loadfrom(PATCH_CONFIG_LOCATION);
        const bool menuSavePending = g_config_apply_pending.exchange(false);
        if (fileChanged || menuSavePending)
            apply_settings();

        {
            const int uiLevel = (int)*(volatile char*)OFF_s_runningUILevel;
            if (uiLevel != lastUiLevel)
            {
                lastUiLevel = uiLevel;
                char msg[64]{};
                snprintf(msg, sizeof(msg), "gate: front-end UI level = %d", uiLevel);
                overlay::DebugLog(msg);
            }

            // [LOCAL] Latch first: from here on, "the engine UI is up" stops
            // depending on the CURRENT level.  A match sets the level back to 0
            // and the scene gate below has to keep ticking through it (see the
            // note where uiEverUp is declared).
            if (lastUiLevel != 0)
                uiEverUp = true;

            // Only safe to call game functions once the game UI is running.
            if (uiEverUp)
            {
                // [LOCAL] Still tied to the CURRENT level, unlike everything
                // below it: this one asks demonware rather than reading a plain
                // engine table, and there is nothing it could report mid-match
                // that the log is missing.
                //
                // Diagnostic only since 2026-09-15: the gate no longer consults
                // the sign-in state (the screen signal replaced it), but the log
                // line is what tells us whether the front-end reached the online
                // lobby at all when something goes wrong.
                if (lastUiLevel != 0)
                {
                    const bool signedIn = Live_IsUserSignedInToDemonware(CONTROLLER_INDEX_0);
                    if (signedIn != lastSignedIn)
                    {
                        lastSignedIn = signedIn;
                        char msg[64]{};
                        snprintf(msg, sizeof(msg), "gate: demonware signed in = %d",
                            signedIn ? 1 : 0);
                        overlay::DebugLog(msg);
                    }
                }

                // [LOCAL] THE gate: real screen detection.  The game resolves the
                // main menu's own labels (the Campaign / Multiplayer / Zombies
                // buttons and the quick-join bar) at render time - measured
                // 2026-09-14 23:16:04, while the title screen only ever resolves
                // "按ENTER开始" and the connecting screen "正在连接到在线服务器".
                // Works online and offline (pure UI text).
                // The title-screen dismissal stays a precondition, so a label the
                // game happens to pre-resolve earlier cannot arm the hotkey.
                // This is the ONLY thing that opens the gate - no timer, see the
                // note before the loop.  NotifyMainMenuReached() is idempotent.
                const unsigned long long dismissed = overlay::TitleScreenDismissedMs();
                // [LOCAL] The verbose UI diagnostics (every distinct UI-model path
                // and UI string) were what found this signal and are off by
                // default: hooks::EnableUiModelPathLog(true) would turn them on
                // again for debugging, and the screen detection itself does not
                // depend on it.
                const bool mainMenuUp = dismissed != 0 && hooks::UiMainMenuSeen();
                // The log line names the signal, so "which branch opened it" is
                // never a guess again (the 2026-09-15 popup took a log dig to
                // attribute because both branches printed the same text).
                if (mainMenuUp)
                    overlay::NotifyMainMenuReached("main-menu label rendered");

                // [LOCAL] The DW_LOBBY / PTR_LobbyVM / s_playerData_ptr value
                // probes and the 24-byte uistate neighbourhood dump that lived
                // here have been removed: they answered their question (none of
                // them separates the "press ENTER" screen from the main menu -
                // see the note before the loop) and only added log noise.

                // [LOCAL] The scene gate: "the player is inside a match in a mode
                // they asked to leave untranslated".
                //
                // This is the one part of the block that also runs while a match
                // is being played, i.e. while s_runningUILevel is back to 0 -
                // that is the whole point of uiEverUp above.  Without it the gate
                // only ever re-evaluated on the way out of a match, so a switch
                // flipped in the menu over a match did nothing until the player
                // returned to the lobby.
                //
                // Two engine FACTS, asked only while translation is on at all -
                // the switches are meaningless while the feature they belong to
                // is off, and this way a switched-off feature costs no engine
                // call and prints no log line:
                //
                //   Com_SessionMode_GetModeName() - the session mode the engine
                //   itself is in.  It returns the two-letter code the upstream
                //   build already compares against ("CP" = Campaign), so "MP" is
                //   Multiplayer and "ZM" is Zombies.
                //
                //   CL_GetConfigString(0) - the server info string, which only
                //   exists once a match has been joined.  That is what separates
                //   "sitting in the Multiplayer menus" (mode is ALREADY "MP",
                //   nothing is joined) from "actually playing".  Only the latter
                //   may be held off: the menus and the lobby are exactly the part
                //   of Multiplayer the dictionary is for.  Zombies has no such
                //   split in practice - its mode is only entered with a match -
                //   but it is asked the same question so both switches mean the
                //   same thing.
                //
                // Both are plain queries made from the MainThread, the only
                // thread this project has ever called engine functions from.  The
                // render thread never sees them - it reads the atomic through
                // translate::Enabled().  Compared with _stricmp rather than
                // Protection::I_stricmp: that function pointer is installed by
                // the patch's own hook setup, and this loop has no business
                // depending on that having happened already.
                if (t7patch_cfg_translate_enabled())
                {
                    char modeBuf[16] = {};
                    const char* mode = Com_SessionMode_GetModeName();
                    if (mode)
                        strncpy_s(modeBuf, sizeof(modeBuf), mode, _TRUNCATE);

                    // Which of the two scene switches this mode is subject to, if
                    // any.  Campaign is in neither list on purpose: it has no
                    // switch and is always translated (nothing there is shared
                    // with other players, so there is nothing to decide).
                    const bool multiplayer = modeBuf[0] != 0 && _stricmp(modeBuf, "MP") == 0;
                    const bool zombies     = modeBuf[0] != 0 && _stricmp(modeBuf, "ZM") == 0;

                    // "Is a match actually being played right now?" - the server
                    // info string only exists once one has been joined.  Asked
                    // only for the two modes that have a switch: nowhere else can
                    // the answer change the outcome, and staying away from the
                    // config-string table the rest of the time keeps this gate's
                    // footprint as small as it can be.
                    bool inMatch = false;
                    if (multiplayer || zombies)
                    {
                        const char* serverInfo = CL_GetConfigString(0);
                        inMatch = serverInfo != nullptr && serverInfo[0] != 0;
                    }

                    // One answer for the layer, two switches behind it.  Note
                    // that the defaults differ (matches off, Zombies on) - that
                    // is the owner's call and lives in the config defaults, not
                    // here.
                    const bool blocked = inMatch
                        && ((multiplayer && t7patch_cfg_skip_pvp())
                            || (zombies && t7patch_cfg_skip_zm()));

                    translate::SetSceneBlocked(blocked);

                    // Logged on every SCENE change, not on every toggle: the
                    // mode string is part of the key on purpose.  It is the
                    // measurement that says whether "MP" and "ZM" really are the
                    // codes these two modes report - if Zombies turned out to
                    // report "MP" (or anything else), its line would say so, and
                    // the Zombies switch is the one that would then never fire.
                    // The answer is not inferable, which is why it is printed.
                    if (blocked != lastSceneBlocked || strcmp(modeBuf, lastSceneMode) != 0)
                    {
                        lastSceneBlocked = blocked;
                        strncpy_s(lastSceneMode, sizeof(lastSceneMode), modeBuf, _TRUNCATE);

                        char msg[192]{};
                        snprintf(msg, sizeof(msg), "scene gate: session mode \"%s\", "
                            "in-match=%d -> translation %s",
                            modeBuf[0] ? modeBuf : "(unreadable)",
                            inMatch ? 1 : 0, blocked ? "off" : "on");
                        overlay::DebugLog(msg);
                    }
                }
                else
                {
                    // Translation is off, so there is nothing to hold off - and
                    // no engine call is made at all.
                    translate::SetSceneBlocked(false);
                    lastSceneBlocked = false;
                }
            }
        }

        Sleep(1000);
    }

    return 0;
}

void load_settings_initial()
{
    // [LOCAL] Cheap and idempotent - DllMain already did this, but the config
    // folder must exist before the very first read/write either way.
    t7patch_ensure_data_dir();

    if (!fs_exists(PATCH_CONFIG_LOCATION))
    {
        user_config.saveto(PATCH_CONFIG_LOCATION);
    }
    else
    {
        user_config.loadfrom(PATCH_CONFIG_LOCATION);

        // [LOCAL] Bring an old config file up to the current format.  Every
        // release that adds a setting leaves the files of players who already
        // had one without it, and loadfrom() deliberately keeps the built-in
        // default for a key the file does not mention - so the setting works,
        // but the file no longer shows the player what there is to configure
        // and goes on looking like this build's format.
        //
        // Rewriting through saveto() loses nothing: it writes the values that
        // were just read, so this is a reformat, not a reset.  It also drops
        // any key this build does not know (the upstream build wrote its own);
        // those were ignored on read anyway, so the file simply ends up
        // agreeing with what the patch actually does.
        //
        // Two older formats reach this code - see the daily log, 2026-09-16 27:
        // the upstream 3-key file (playername / isfriendsonly /
        // networkpassword, no comments) and this fork's 7-key one from before
        // the translation switches.  The owner's call, 2026-09-16: "if the file
        // does not match, just generate a new one and overwrite the old".
        unsigned missingKeys = 0;
        bool readFailed = false;
        {
            std::lock_guard<std::mutex> lock(g_config_mutex);
            missingKeys = patch_config::K_ALL & ~user_config.keys_seen;
            readFailed = user_config.read_failed;
        }

        if (missingKeys != 0 && readFailed)
        {
            // [LOCAL] The file is there but could not be opened (an AV scanner
            // holding it, a deny-ACL, a syncing drive).  Rewriting now would
            // wipe the player's settings with this build's defaults - and
            // saveto() would then mark the file complete, so nothing would
            // ever put them back.  Leave the file alone: for this session the
            // values in force are the built-in defaults, exactly as before.
            overlay::DebugLog("config file is present but could not be read - "
                "left untouched (locked by another program?)");
        }
        else if (missingKeys != 0)
        {
            int missingCount = 0;
            for (unsigned bit = 1; bit <= patch_config::K_ALL; bit <<= 1)
            {
                if (missingKeys & bit)
                    ++missingCount;
            }

            if (user_config.saveto(PATCH_CONFIG_LOCATION))
            {
                char msg[160];
                snprintf(msg, sizeof(msg), "config file was in an older format "
                    "(%d setting(s) missing) - rewritten in the current format",
                    missingCount);
                overlay::DebugLog(msg);
            }
            else
            {
                // Not fatal: the settings are live for this session either way,
                // only the file keeps the old shape.  Worth a line so "why does
                // my conf still look old" is answerable from the log.
                overlay::DebugLog("config file is outdated but could not be rewritten "
                    "- is the T7Patch folder writable?");
            }
        }
    }

    // [LOCAL] Persist the start-up language gate's decision (2026-09-16; the
    // owner's call was "just switch it off - the menu switch is how you turn it
    // back on").
    //
    // The gate itself lives in translate.cpp and has already run: the Init that
    // RunPatching() calls before this function latches the switch off in memory
    // when the game is not running Chinese.  A latch alone left
    // translate=1 sitting in the conf file, which reads exactly like the setting
    // was ignored, so the decision is written down HERE.
    //
    // Why here: this is the first moment the conf is known to be loaded (the
    // loadfrom above), so a save cannot clobber the rest of the file with
    // constructor defaults; and it keeps translate.cpp, which runs from the
    // engine path, free of file writes.
    //
    // g_translate_persist_request is only set for a language that was actually
    // read.  An unreadable localization.txt still latches the layer off for the
    // session (fail closed) but does not rewrite the player's file on a guess.
    if (g_translate_persist_request.exchange(false))
    {
        bool changed = false;
        {
            std::lock_guard<std::mutex> lock(g_config_mutex);
            if (user_config.translate != 0)
            {
                user_config.translate = 0;
                changed = true;
            }
        }
        if (changed)
        {
            user_config.saveto(PATCH_CONFIG_LOCATION);
            overlay::DebugLog("start-up language gate: mod translation switched off in the config");
        }
    }

    apply_settings();
}

__int64 old_IsProcessorFeaturePresent = 0;

void Protection::install()
{
    // [LOCAL] One-shot gate.  install() has two entry points - the proxy's
    // PatchWorker (CAS-guarded in Proxy.cpp) and the exported
    // zbr_run_gamemode_lui, which has no guard at all - and a second pass is
    // destructive rather than merely redundant:
    //   * IHOOK_INSTALL(IsProcessorFeaturePresent, ...) assigns
    //     oIsProcessorFeaturePresent from detour_iat_ptr(), which returns 0
    //     when the slot already points at our hook (Protection.cpp find()/
    //     detour_iat_ptr, "already ours" branch).  The live hook would then
    //     call a NULL original pointer.
    //   * the injectorless branch at the end of this function starts a second
    //     MainThread, i.e. two 1 Hz watchers applying settings and running the
    //     Arxan bypass maintenance.
    // Nothing in here is idempotent, so ignoring the repeat IS the fix.
    static std::atomic<bool> installDone{ false };
    if (installDone.exchange(true))
    {
        overlay::DebugLog("install() already ran in this process - ignoring the repeat");
        return;
    }

    LobbyMsgRW_PackageInt = (tLobbyMsgRW_PackageInt)PTR_LobbyMsgRW_PackageInt;
    LobbyMsgRW_PackageUChar = (tLobbyMsgRW_PackageUChar)PTR_LobbyMsgRW_PackageUChar;
    LobbyMsgRW_PackageString = (tLobbyMsgRW_PackageString)PTR_LobbyMsgRW_PackageString;
    LobbyMsgRW_PackageXuid = (tLobbyMsgRW_PackageXuid)PTR_LobbyMsgRW_PackageXuid;
    LobbyMsgRW_PackageBool = (tLobbyMsgRW_PackageBool)PTR_LobbyMsgRW_PackageBool;
    LobbyMsgRW_PackageUInt = (tLobbyMsgRW_PackageUInt)PTR_LobbyMsgRW_PackageUInt;
    LobbyMsgRW_PackageShort = (tLobbyMsgRW_PackageShort)PTR_LobbyMsgRW_PackageShort;
    LobbyMsgRW_PackageUInt64 = (tLobbyMsgRW_PackageUInt64)PTR_LobbyMsgRW_PackageUInt64;
    LobbyMsgRW_PackageArrayStart = (tLobbyMsgRW_PackageArrayStart)PTR_LobbyMsgRW_PackageArrayStart;
    LobbyMsgRW_PackageElement = (tLobbyMsgRW_PackageElement)PTR_LobbyMsgRW_PackageElement;
    LobbyMsgRW_PackageGlob = (tLobbyMsgRW_PackageGlob)PTR_LobbyMsgRW_PackageGlob;
    MsgMutableClientInfo_Package = (tMsgMutableClientInfo_Package)PTR_MsgMutableClientInfo_Package;
    ProbeLobbyInfo = (tProbeLobbyInfo)PTR_ProbeLobbyInfo;
    dwInstantHandleLobbyMessage = (tdwInstantHandleLobbyMessage)PTR_dwInstantHandleLobbyMessage;
    NET_OutOfBandPrint = (tNET_OutOfBandPrint)PTR_NET_OutOfBandPrint;
    dwCommonAddrToNetadr = (tdwCommonAddrToNetadr)PTR_dwCommonAddrToNetadr;
    dwRegisterSecIDAndKey = (tdwRegisterSecIDAndKey)PTR_dwRegisterSecIDAndKey;
    LobbyMsgRW_PrepWriteMsg = (tLobbyMsgRW_PrepWriteMsg)PTR_LobbyMsgRW_PrepWriteMsg;
    LobbyMsgRW_PackageUShort = (tLobbyMsgRW_PackageUShort)PTR_LobbyMsgRW_PackageUShort;
    LobbyMsgRW_PackageFloat = (tLobbyMsgRW_PackageFloat)PTR_LobbyMsgRW_PackageFloat;
    MSG_Init = (tMSG_Init)PTR_MSG_Init;
    MSG_WriteString = (tMSG_WriteString)PTR_MSG_WriteString;
    MSG_WriteShort = (tMSG_WriteShort)PTR_MSG_WriteShort;
    MSG_WriteByte = (tMSG_WriteByte)PTR_MSG_WriteByte;
    MSG_WriteData = (tMSG_WriteData)PTR_MSG_WriteData;
    Com_ControllerIndex_GetLocalClientNum = (tCom_ControllerIndex_GetLocalClientNum)PTR_Com_ControllerIndex_GetLocalClientNum;
    Com_LocalClient_GetNetworkID = (tCom_LocalClient_GetNetworkID)PTR_Com_LocalClient_GetNetworkID;
    NET_OutOfBandData = (tNET_OutOfBandData)PTR_NET_OutOfBandData;
    LobbyMsgTransport_SendToAdr = (tLobbyMsgTransport_SendToAdr)PTR_LobbyMsgTransport_SendToAdr;
    MSG_ReadData = (tMSG_ReadData)PTR_MSG_ReadData;
    LobbyMsgRW_PrepReadData = (tLobbyMsgRW_PrepReadData)PTR_LobbyMsgRW_PrepReadData;
    MSG_InfoResponse = (tMSG_InfoResponse)PTR_MSG_InfoResponse;
    LobbyMsgRW_PackageChar = (tLobbyMsgRW_PackageChar)PTR_LobbyMsgRW_PackageChar;
    I_stricmp = (tI_stricmp)PTR_I_stricmp;
    dwInstantSendMessage = (tdwInstantSendMessage)PTR_dwInstantSendMessage;
    LobbySession_GetControllingLobbySession = (tLobbySession_GetControllingLobbySession)PTR_LobbySession_GetControllingLobbySession;
    LobbySession_GetSession = (tLobbySession_GetSession)PTR_LobbySession_GetSession;
    LobbySession_GetClientByClientNum = (tLobbySession_GetClientByClientNum)PTR_LobbySession_GetClientByClientNum;
    LobbySession_GetClientNetAdrByIndex = (tLobbySession_GetClientNetAdrByIndex)PTR_LobbySession_GetClientNetAdrByIndex;
    LobbyJoin_Reserve = (tLobbyJoin_Reserve)PTR_LobbyJoin_Reserve;
    CL_GetConfigString = (tCL_GetConfigString)PTR_CL_GetConfigString;
    Cbuf_AddText = (tCbuf_AddText)PTR_Cbuf_AddText;
    I_stricmp = (tI_stricmp)PTR_I_stricmp;
    CachedXUID = **(__int64**)s_playerData_ptr;

    SetNetworkPassword(0);

    sMstart = "mstart";
    sMdata = "mdata";
    sMhead = "mhead";
    sMstate = "mstate";
    sConnectResponse = "connectResponseMigration";
    sRcon = "rcon";
    sRequestStats = "requeststats";
    sRequestStats2 = "requeststats\n";
    sLoading = "loadingnewmap";
    sRA = "RA";
    sV = "v";
    sVT = "vt";
    sRelay = "relay";
    sLMGI = "LMgetinfo";

    SS(targetlobby)
    SS(sourcelobby)
    SS(jointype)
    SS(probedxuid)
    SS(playlistid)
    SS(playlistver)
    SS(ffotdver)
    SS(networkmode)
    SS(netchecksum)
    SS(protocol)
    SS(changelist)
    SS(pingband)
    SS(dlcbits)
    SS(joinnonce)
    SS(chunk)
    SS(isStarterPack)
    SS(password)
    SS(membercount)
    SS(members)
    SS(xuid)
    SS(lobbyid)
    SS(skillrating)
    SS(skillvariance)
    SS(pprobation)
    SS(aprobation)
    SS(statenum)
    SS(mainmode)
    SS(partyprivacy)
    SS(lobbytype)
    SS(lobbymode)
    SS(sessionstatus)
    SS(uiscreen)
    SS(leaderactivity)
    SS(key)
    SS(leader)
    SS(platformsession)
    SS(maxclients)
    SS(isadvertised)
    SS(clientcount)
    SS(sessionid)
    SS(sessioninfo)
    SS(ugcName)
    SS(ugcVersion)
    SS(clientlist)
    SS(clientNum)
    SS(gamertag)
    SS(isGuest)
    SS(connectbit)
    SS(score)
    SS(address)
    SS(qport)
    SS(band)
    SS(netsrc)
    SS(joinorder)
    SS(dlcBits)
    SS(migratebits)
    SS(lasthosttimems)
    SS(nomineelist)
    // [LOCAL] SS(x) expands to "s##x = #x;", so the two duplicate lines that
    // used to sit here just re-assigned sdlcBits twice.  Harmless, but noise.
    SS(dlcBits)
    SS(serverstatus)
    SS(launchnonce)
    SS(matchhashlow)
    SS(matchhashhigh)
    SS(status)
    SS(statusvalue)
    SS(gamemode)
    SS(gametype)
    SS(map)
    SS(cpqueuedlevel)
    SS(movieskipped)
    SS(team)
    SS(mapvote)
    SS(readyup)
    SS(plistid)
    SS(plistcurr)
    SS(plistentries)
    SS(plistnext)
    SS(plistprev)
    SS(plistprevcount)
    SS(votecount)
    SS(votes)
    SS(itemtype)
    SS(item)
    SS(itemgroup)
    SS(attachment)
    SS(votetype)
    SS(votexuid)
    SS(pregamepos)
    SS(pregamestate)
    SS(clvotecount)
    SS(character)
    SS(loadout)
    SS(settingssize)
    SS(compstate)
    SS(heartbeatnum)
    SS(nonce)
    SS(nattype)
    SS(lobbies)
    SS(valid)
    SS(hostxuid)
    SS(hostname)
    SS(secid)
    SS(seckey)
    SS(addrbuff)

    if (*CustomName)
    {
        memcpy((void*)REBASE(0x15E84638), CustomName, strlen(CustomName) + 1);
        memcpy((void*)PTR_Name1, CustomName, strlen(CustomName) + 1);
        memcpy((void*)PTR_Name2, CustomName, strlen(CustomName) + 1);
        if (!IsBadReadPtr((VOID*)s_playerData_ptr) && *(INT64*)s_playerData_ptr)
        {
            memset((void*)(*(INT64*)s_playerData_ptr + 0x8), 0, 16);
            memcpy((void*)(*(INT64*)s_playerData_ptr + 0x8), CustomName, strlen(CustomName) + 1);
        }
    }

    old_IsProcessorFeaturePresent = (__int64)&IsProcessorFeaturePresent;

    oReadP2PPacket = (decltype(&ReadP2PPacket))((*(__int64*)(STEAMAPI_NETWORKING + 0x10)));
    IHOOK_INSTALL(IsProcessorFeaturePresent, GetModuleHandleA(0));

    SwapSteamAPIPointer(STEAMAPI_STEAMUSER, STEAMAPI_STEAMUSER_GETUSERNAME, GetUsernamePtr);
    SwapSteamAPIPointer(STEAMAPI_STEAMUSER, STEAMAPI_STEAMUSER_VT_NAMEBYXUID, GetUsernameXUIDPtr);

    SwapSteamAPIPointer(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_CHECK_OWNS_CONTENT, GetOwnsContent);
    SwapSteamAPIPointer(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_CHECK_OWNS_CONTENT2, GetOwnsContent2);
    SwapSteamAPIPointer(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_IS_VAC_BANNED, IsVacBanned);
    SwapSteamAPIPointer(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_GET_DLC_DOWNLOAD_PROGRESS, GetDlcDownloadProgress);

    SwapSteamAPIPointer(STEAMAPI_MATCHMAKING, STEAMAPI_MATCHMAKING_GETLOBBYCHATENTRY, GetLobbyChatEntry);
    SwapSteamAPIPointer(STEAMAPI_MATCHMAKING, STEAMAPI_MATCHMAKING_CREATELOBBY, CreateLobby);
    SwapSteamAPIPointer(STEAMAPI_NETWORKING, STEAMAPI_NETWORKING_READP2PPACKET, ReadP2PPacket);

    *(__int64*)PTR_UpdatePreloadIdleFN = (INT64)CL_SwitchState_Idle_Update;


    // join party
    Protection::handle_packet_callbacks[0x10] = [](__int32* lobbyMsgTypePtr, __int64 lobbyMsg)
        {
            memset(requestOut, 0, sizeof(requestOut));
            memset(lobbyMsgCpy, 0, sizeof(lobbyMsgCpy));
            memcpy_s(lobbyMsgCpy, sizeof(lobbyMsgCpy), (void*)lobbyMsg, 0x44);

            auto result = MSG_JoinParty_Package_Inspect(requestOut, lobbyMsgCpy);
            if (result)
            {
                // crash attempt
                *lobbyMsgTypePtr = 0xFF; // drop

            }
        };

    // modified stats
    Protection::handle_packet_callbacks[0xF] = [](__int32* lobbyMsgTypePtr, __int64 lobbyMsg)
        {
            *lobbyMsgTypePtr = 0xFF; // drop
        };

    // auto-drops
    Protection::handle_packet_callbacks[0x1E] = Protection::handle_packet_callbacks[0xF];
    Protection::handle_packet_callbacks[0x16] = Protection::handle_packet_callbacks[0xF];
    Protection::handle_packet_callbacks[0x17] = Protection::handle_packet_callbacks[0xF];
    Protection::handle_packet_callbacks[0x18] = Protection::handle_packet_callbacks[0xF];

    Protection::handle_packet_callbacks[MESSAGE_TYPE_LOBBY_HOST_HEARTBEAT] = [](__int32* lobbyMsgTypePtr, __int64 lobbyMsg)
        {
            memset(requestOut, 0, sizeof(requestOut));
            memset(lobbyMsgCpy, 0, sizeof(lobbyMsgCpy));
            memcpy_s(lobbyMsgCpy, sizeof(lobbyMsgCpy), (void*)lobbyMsg, 0x44);
            __int32* _this = (__int32*)requestOut;

            BOOL packageOK =
                LobbyMsgRW_PackageInt((void*)lobbyMsgCpy, "heartbeatnum", (__int32*)_this) &&
                LobbyMsgRW_PackageInt((void*)lobbyMsgCpy, "lobbytype", (__int32*)_this) &&
                LobbyMsgRW_PackageInt((void*)lobbyMsgCpy, "lasthosttimems", (__int32*)_this);

            if (!packageOK)
            {
                return;
            }

            LobbyMsgRW_PackageArrayStart((void*)lobbyMsgCpy, "nomineelist");

            unsigned __int64 xuidValue = 1;
            for (int i = 0; i < 0x12; i++)
            {
                bool res = LobbyMsgRW_PackageElement((void*)lobbyMsgCpy, true);
                if (!res)
                {
                    return;
                }
                res = LobbyMsgRW_PackageXuid((void*)lobbyMsgCpy, "xuid", &xuidValue);

                if (!res)
                {
                    return;
                }
            }

            if (LobbyMsgRW_PackageElement((void*)lobbyMsgCpy, true))
            {
                *lobbyMsgTypePtr = 0xFF;
            }
        };

    Protection::handle_packet_callbacks[0x2] = [](__int32* lobbyMsgTypePtr, __int64 lobbyMsg)
        {
            memset(requestOut, 0, sizeof(requestOut));
            memset(lobbyMsgCpy, 0, sizeof(lobbyMsgCpy));
            memcpy_s(lobbyMsgCpy, sizeof(lobbyMsgCpy), (void*)lobbyMsg, 0x44);

            auto result = MSG_LobbyState_Package_Inspect(requestOut, lobbyMsgCpy);
            if (result)
            {
                // crash attempt
                *lobbyMsgTypePtr = 0xFF;
            }
        };

    Protection::handle_packet_callbacks[0x3] = [](__int32* lobbyMsgTypePtr, __int64 lobbyMsg)
        {
            memset(requestOut, 0, sizeof(requestOut));
            memset(lobbyMsgCpy, 0, sizeof(lobbyMsgCpy));
            memcpy_s(lobbyMsgCpy, sizeof(lobbyMsgCpy), (void*)lobbyMsg, 0x44);

            auto result = MSG_LobbyStateGame_Package_Inspect(requestOut, lobbyMsgCpy);
            if (result)
            {
                // crash attempt
                *lobbyMsgTypePtr = 0xFF;
            }
        };

    Protection::Old_lobbymsgprints = *(__int64*)PTR_lobbymsgprints;
    *(__int64*)PTR_lobbymsgprints = 0xFFEEDDCC44332212;
    Protection::CachedRetnAddy = PTR_saveLobbyMsgExceptAddy;

    // Call create lobby again
    ((void(__fastcall*)(__int64))REBASE(0x1EA6010))(REBASE(0x113A4A60));

    INT64 ptrDvar = *(INT64*)(REBASE(0x1686ED20));
    *(DWORD*)(ptrDvar + 0x18) = 0; // clear flags

    Dvar_SetFromStringByName("ui_error_callstack_ship", "1", true);

    ptrDvar = *(INT64*)(REBASE(0xA0378B8));
    *(DWORD*)(ptrDvar + 0x18) = 0; // clear flags

    Dvar_SetFromStringByName("g_allowvote", "0", true);

    //Dvar_SetFromStringByName("sv_mapswitch", "0", true); // Caused inf black screen when loading campaign maps.

    // [LOCAL] removed: maxvoicepacketsperframe=0 disabled in-game voice processing
    // for a negligible CPU saving; keeping in-game voice working is worth more.

    if (IsInjectorlessInstall)
    {
        load_settings_initial();
        CreateThread(nullptr, 0, MainThread, nullptr, 0, nullptr);
    }
}

void Protection::uninstall()
{
    *(__int64*)PTR_lobbymsgprints = Protection::Old_lobbymsgprints;
    SetNetworkPassword(0);
    Iat_hook_::detour_iat_ptr("IsProcessorFeaturePresent", (void*)old_IsProcessorFeaturePresent);

    SwapSteamAPIPointer(STEAMAPI_STEAMUSER, STEAMAPI_STEAMUSER_GETUSERNAME, (void*)GetOriginalSteamPtr(STEAMAPI_STEAMUSER, STEAMAPI_STEAMUSER_GETUSERNAME));
    SwapSteamAPIPointer(STEAMAPI_STEAMUSER, STEAMAPI_STEAMUSER_VT_NAMEBYXUID, (void*)GetOriginalSteamPtr(STEAMAPI_STEAMUSER, STEAMAPI_STEAMUSER_VT_NAMEBYXUID));

    SwapSteamAPIPointer(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_CHECK_OWNS_CONTENT, (void*)GetOriginalSteamPtr(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_CHECK_OWNS_CONTENT));
    SwapSteamAPIPointer(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_CHECK_OWNS_CONTENT2, (void*)GetOriginalSteamPtr(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_CHECK_OWNS_CONTENT2));
    SwapSteamAPIPointer(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_IS_VAC_BANNED, (void*)GetOriginalSteamPtr(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_IS_VAC_BANNED));
    SwapSteamAPIPointer(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_GET_DLC_DOWNLOAD_PROGRESS, (void*)GetOriginalSteamPtr(STEAMAPI_INTERFACE, STEAMAPI_INTERFACE_GET_DLC_DOWNLOAD_PROGRESS));

    SwapSteamAPIPointer(STEAMAPI_MATCHMAKING, STEAMAPI_MATCHMAKING_GETLOBBYCHATENTRY, (void*)GetOriginalSteamPtr(STEAMAPI_MATCHMAKING, STEAMAPI_MATCHMAKING_GETLOBBYCHATENTRY));
    SwapSteamAPIPointer(STEAMAPI_MATCHMAKING, STEAMAPI_MATCHMAKING_CREATELOBBY, (void*)GetOriginalSteamPtr(STEAMAPI_MATCHMAKING, STEAMAPI_MATCHMAKING_CREATELOBBY));
    SwapSteamAPIPointer(STEAMAPI_NETWORKING, STEAMAPI_NETWORKING_READP2PPACKET, (void*)GetOriginalSteamPtr(STEAMAPI_NETWORKING, STEAMAPI_NETWORKING_READP2PPACKET));

    *(__int64*)PTR_UpdatePreloadIdleFN = REBASE(0x131E350);
}

char Protection::requestOut[0x20000]{};
char Protection::lobbyMsgCpy[0x50]{};
void Protection::InspectLM(PEXCEPTION_RECORD ExceptionRecord, PCONTEXT ContextRecord)
{
    __int64 retnAddy = *(__int64*)(ContextRecord->Rsp + 0x28);

    // we expect a very specific return addy to operate on
    if (retnAddy != CachedRetnAddy)
    {
        goto ExitCleanly;
    }

    {
        __int64 ctxSuperRsp = ContextRecord->Rsp + 0x30; // calc old Rsp
        __int64 ctxSuperRbx = *(__int64*)(ContextRecord->Rsp + 0x20); // grab old rbx off the stack
        __int32 msgType = *(__int32*)(ctxSuperRsp + 0xB0); // grab the message type [0=host,1=client,3=peer]
        __int64 lobbyMsg = (ctxSuperRsp + 0x88 - 0x58); // lobby message is on the stack (its a LEA)
        __int32* lobbyMsgTypePtr = (__int32*)(lobbyMsg + 0x38);
        __int32 lobbyMsgType = *lobbyMsgTypePtr;

        if (Protection::handle_packet_callbacks.find(lobbyMsgType) != Protection::handle_packet_callbacks.end())
        {
            Protection::handle_packet_callbacks[lobbyMsgType](lobbyMsgTypePtr, lobbyMsg);
            if (*lobbyMsgTypePtr == 0xFF)
            {
                //XLOG("^6DROPPED LOBBYMESSAGE %d", lobbyMsgType);
            }
        }
    }

ExitCleanly:
    ContextRecord->Rcx = Protection::Old_lobbymsgprints;
    ContextRecord->Rbx = Protection::Old_lobbymsgprints;
}

int Protection::MSG_JoinParty_Package_Inspect(char* _this, char* lobbyMsg)
{
    BOOL packageOK =
        LobbyMsgRW_PackageInt(lobbyMsg, "targetlobby", (__int32*)_this)
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(sourcelobby), (__int32*)(_this + 4))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(jointype), (__int32*)(_this + 8))
        && LobbyMsgRW_PackageXuid(lobbyMsg, STR(probedxuid), (unsigned __int64*)(_this + 16))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(playlistid), (__int32*)(_this + 612))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(playlistver), (__int32*)(_this + 616))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(ffotdver), (__int32*)(_this + 620))
        && LobbyMsgRW_PackageShort(lobbyMsg, STR(networkmode), (__int16*)(_this + 624))
        && LobbyMsgRW_PackageUInt(lobbyMsg, STR(netchecksum), (unsigned __int32*)(_this + 628))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(protocol), (__int32*)(_this + 632))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(changelist), (__int32*)(_this + 636))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(pingband), (__int32*)(_this + 640))
        && LobbyMsgRW_PackageUInt(lobbyMsg, STR(dlcbits), (unsigned __int32*)(_this + 644))
        && LobbyMsgRW_PackageUInt64(lobbyMsg, STR(joinnonce), (unsigned __int64*)(_this + 648));

    for (int i = 0; packageOK && (i < 3); i++)
    {
        packageOK = packageOK && LobbyMsgRW_PackageUChar(lobbyMsg, STR(chunk), (char*)(_this + i + 689));
    }

    packageOK = packageOK &&
        LobbyMsgRW_PackageBool(lobbyMsg, STR(isStarterPack), (char*)(_this + 656))
        && LobbyMsgRW_PackageString(lobbyMsg, STR(password), (char*)(_this + 657), 0x20)
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(membercount), (__int32*)(_this + 24))
        && LobbyMsgRW_PackageArrayStart(lobbyMsg, STR(members));

    if (!packageOK)
    {
        // bad packet
        return 1;
    }

    if (*(__int32*)(_this + 24) > 18)
    {
        // crash attempt via BoF
        return 2;
    }

    if (LobbyMsgRW_PackageElement(lobbyMsg, *(__int32*)(_this + 24) > 0))
    {
        if (*(__int32*)(_this + 24) <= 0) // this is an element even though the packet claims to have 0 members... BoF attempt!
        {
            // crash attempt via BoF
            return 3;
        }

        for (int i = 0; i < *(__int32*)(_this + 24); i++)
        {
            packageOK = packageOK
                && LobbyMsgRW_PackageXuid(lobbyMsg, STR(xuid), (unsigned __int64*)(_this + 616))
                && LobbyMsgRW_PackageUInt64(lobbyMsg, STR(lobbyid), (unsigned __int64*)(_this + 616))
                && LobbyMsgRW_PackageFloat(lobbyMsg, STR(skillrating), (float*)(_this + 616))
                && LobbyMsgRW_PackageFloat(lobbyMsg, STR(skillvariance), (float*)(_this + 616))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(pprobation), (unsigned __int32*)(_this + 616))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(aprobation), (unsigned __int32*)(_this + 616));

            if (!packageOK)
            {
                return 4; // bad packet
            }

            bool expected = (i + 1) < *(__int32*)(_this + 24);
            bool result = LobbyMsgRW_PackageElement(lobbyMsg, expected);
            if (result && !expected)
            {
                return 5; // BoF attempt via package element overflow
            }
        }
    }

    return 0; // packet is fine
}

int Protection::MSG_LobbyState_Package_Inspect(char* __this, char* lobbyMsg)
{
    __int32* _this = (__int32*)__this;

    BOOL packageOK =
        LobbyMsgRW_PackageInt(lobbyMsg, STR(statenum), (__int32*)_this)
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(networkmode), (__int32*)(_this + 1))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(mainmode), (__int32*)(_this + 2))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(partyprivacy), (__int32*)(_this + 3))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(lobbytype), (__int32*)(_this + 4))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(lobbymode), (__int32*)(_this + 5))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(sessionstatus), (__int32*)(_this + 6))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(uiscreen), (__int32*)(_this + 7))
        && LobbyMsgRW_PackageUChar(lobbyMsg, STR(leaderactivity), (char*)_this + 32)
        && LobbyMsgRW_PackageString(lobbyMsg, STR(key), (char*)(_this + 9), 0x20)
        && LobbyMsgRW_PackageXuid(lobbyMsg, STR(leader), (unsigned __int64*)(_this + 9))
        && LobbyMsgRW_PackageXuid(lobbyMsg, STR(platformsession), (unsigned __int64*)(_this + 10))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(maxclients), (__int32*)(_this + 22))
        && LobbyMsgRW_PackageBool(lobbyMsg, STR(isadvertised), (char*)_this + 92)
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(clientcount), (__int32*)(_this + 24))
        && LobbyMsgRW_PackageString(lobbyMsg, STR(sessionid), (char*)(_this + 5320), 0x40)
        && LobbyMsgRW_PackageString(lobbyMsg, STR(sessioninfo), (char*)(_this + 5336), 0x40)
        && LobbyMsgRW_PackageString(lobbyMsg, STR(ugcName), (char*)(_this + 5352), 0x20)
        && LobbyMsgRW_PackageUInt(lobbyMsg, STR(ugcVersion), (unsigned __int32*)(_this + 5360));

    if (!packageOK)
    {
        // bad packet
        return 1;
    }

    LobbyMsgRW_PackageArrayStart(lobbyMsg, STR(clientlist));

    if (_this[24] > 18)
    {
        // crash attempt via BoF
        return 2;
    }

    int index = 0;
    bool hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, index < _this[24]);


    while (hasNextElement && index < _this[24])
    {
        __int32 offset = 292 * index;
        __int64 offset2 = (__int64)&_this[offset + 26];

        packageOK = packageOK
            && LobbyMsgRW_PackageXuid(lobbyMsg, STR(xuid), (unsigned __int64*)(offset2))
            && LobbyMsgRW_PackageUChar(lobbyMsg, STR(clientNum), (char*)(offset2 + 8))
            && LobbyMsgRW_PackageString(lobbyMsg, STR(gamertag), (char*)(offset2 + 9), 0x20)
            && LobbyMsgRW_PackageBool(lobbyMsg, STR(isGuest), (char*)(offset2 + 41))
            && LobbyMsgRW_PackageUInt64(lobbyMsg, STR(lobbyid), (unsigned __int64*)(offset2 + 48))
            && LobbyMsgRW_PackageInt(lobbyMsg, STR(connectbit), (__int32*)(offset2 + 1108))
            && LobbyMsgRW_PackageInt(lobbyMsg, STR(score), (__int32*)(offset2 + 1104))
            && LobbyMsgRW_PackageGlob(lobbyMsg, STR(address), (char*)(offset2 + 1113), 37)
            && LobbyMsgRW_PackageInt(lobbyMsg, STR(qport), (__int32*)(offset2 + 56))
            && LobbyMsgRW_PackageUChar(lobbyMsg, STR(band), (char*)(offset2 + 60))
            && LobbyMsgRW_PackageUInt(lobbyMsg, STR(netsrc), (unsigned __int32*)(offset2 + 1152))
            && LobbyMsgRW_PackageUInt(lobbyMsg, STR(joinorder), (unsigned __int32*)(offset2 + 1156))
            && LobbyMsgRW_PackageUInt(lobbyMsg, STR(dlcBits), (unsigned __int32*)(offset2 + 1160))
            && MsgMutableClientInfo_Package((char*)(offset2 + 64), lobbyMsg);

        if (!packageOK)
        {
            return 100 + 1; // bad packet
        }

        index++;
        hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, index < _this[24]);
    }

    if (hasNextElement)
    {
        return 100 + 2; // Crash attempt via BoF and PackElem RO exploit
    }

    packageOK = packageOK
        && LobbyMsgRW_PackageUChar(lobbyMsg, STR(migratebits), (char*)_this + 21128)
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(lasthosttimems), (__int32*)(_this + 5283));

    if (!packageOK)
    {
        // bad packet
        return 3;
    }

    LobbyMsgRW_PackageArrayStart(lobbyMsg, STR(nomineelist));

    __int32 count = 0;
    hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (count < 18));

    while (hasNextElement && (count < 18))
    {
        packageOK = packageOK && LobbyMsgRW_PackageXuid(lobbyMsg, STR(xuid), (unsigned __int64*)(&_this[0x14A4 + (2 * count)]));
        count++;
        hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (count < 18));
    }

    if (hasNextElement)
    {
        return 100 + 3; // crash attempt via PERO nominee
    }

    if (!packageOK)
    {
        // bad packet
        return 4;
    }

    return 0;
}

int Protection::MSG_LobbyStateGame_Package_Inspect(char* __this, char* lobbyMsg)
{
    int lspiResult = MSG_LobbyState_Package_Inspect(__this, lobbyMsg);

    if (lspiResult)
    {
        return lspiResult;
    }

    __int32* _this = (__int32*)__this;
    bool packageOK = LobbyMsgRW_PackageInt(lobbyMsg, STR(serverstatus), (__int32*)(_this + 5362));

    if (!packageOK)
    {
        return 11;
    }

    packageOK = packageOK
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(launchnonce), (__int32*)(_this + 5363))
        && LobbyMsgRW_PackageUInt64(lobbyMsg, STR(matchhashlow), (unsigned __int64*)(_this + 2682))
        && LobbyMsgRW_PackageUInt64(lobbyMsg, STR(matchhashhigh), (unsigned __int64*)(_this + 2683))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(status), (__int32*)(_this + 5394))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(statusvalue), (__int32*)(_this + 5395))
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(gamemode), (__int32*)(_this + 5368))
        && LobbyMsgRW_PackageString(lobbyMsg, STR(gametype), (char*)(_this + 5369), 0x20)
        && LobbyMsgRW_PackageString(lobbyMsg, STR(map), (char*)(_this + 5377), 0x20)
        && LobbyMsgRW_PackageString(lobbyMsg, STR(ugcName), (char*)(_this + 5385), 0x20)
        && LobbyMsgRW_PackageUInt(lobbyMsg, STR(ugcVersion), (unsigned __int32*)(_this + 5393));

    if (!_this[2])
    {
        packageOK = packageOK
            && LobbyMsgRW_PackageString(lobbyMsg, STR(cpqueuedlevel), (char*)(_this + 7293), 0x20)
            && LobbyMsgRW_PackageBool(lobbyMsg, STR(movieskipped), (char*)_this + 29204);
    }

    __int32 lobbyMode = _this[5];

    if (!lobbyMode)
    {
        LobbyMsgRW_PackageArrayStart(lobbyMsg, STR(clientlist));
        int index = 0;
        bool hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < 18));
        while (hasNextElement && (index < 18))
        {
            __int64 currentClient = (__int64)&_this[9 * index];
            packageOK = packageOK
                && LobbyMsgRW_PackageInt(lobbyMsg, STR(team), (__int32*)(currentClient + 28524))
                && LobbyMsgRW_PackageInt(lobbyMsg, STR(mapvote), (__int32*)(currentClient + 28528))
                && LobbyMsgRW_PackageBool(lobbyMsg, STR(readyup), (char*)(currentClient + 28532));

            if (!packageOK)
            {
                // bad pack
                return 20 + 1;
            }

            index++;
            hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < 18));
        }

        if (hasNextElement)
        {
            // PERO
            return 20 + 2;
        }

        packageOK = packageOK
            && LobbyMsgRW_PackageInt(lobbyMsg, STR(plistid), (__int32*)(_this + 7126))
            && LobbyMsgRW_PackageInt(lobbyMsg, STR(plistcurr), (__int32*)(_this + 7127))
            && LobbyMsgRW_PackageGlob(lobbyMsg, STR(plistentries), (char*)_this + 28512, 8)
            && LobbyMsgRW_PackageUChar(lobbyMsg, STR(plistnext), (char*)_this + 28520)
            && LobbyMsgRW_PackageUChar(lobbyMsg, STR(plistprev), (char*)_this + 28521)
            && LobbyMsgRW_PackageUChar(lobbyMsg, STR(plistprevcount), (char*)_this + 28522);

        if (!packageOK)
        {
            // bad packet
            return 5;
        }

        goto PackageOK;
    }

    lobbyMode--;
    if (!lobbyMode)
    {
        packageOK = packageOK && LobbyMsgRW_PackageInt(lobbyMsg, STR(votecount), (__int32*)(_this + 5397));
        LobbyMsgRW_PackageArrayStart(lobbyMsg, STR(votes));

        int numVotes = *(__int32*)(_this + 5397);
        if (packageOK && (numVotes > 216))
        {
            // crash attempt via votecount BoF
            return 20 + 6;
        }

        int index = 0;
        bool hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < numVotes));

        while (hasNextElement && (index < numVotes))
        {
            __int64 currentVote = (__int64)(&_this[8 * index + 5398]);
            packageOK = packageOK
                && LobbyMsgRW_PackageShort(lobbyMsg, STR(itemtype), (__int16*)(currentVote + 8))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(item), (unsigned int*)(currentVote + 12))
                && LobbyMsgRW_PackageShort(lobbyMsg, STR(itemgroup), (__int16*)(currentVote + 16))
                && LobbyMsgRW_PackageShort(lobbyMsg, STR(attachment), (__int16*)(currentVote + 20))
                && LobbyMsgRW_PackageShort(lobbyMsg, STR(votetype), (__int16*)(currentVote + 24))
                && LobbyMsgRW_PackageXuid(lobbyMsg, STR(votexuid), (unsigned __int64*)(currentVote));

            if (!packageOK)
            {
                return 6; // bad packet
            }

            index++;
            hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < numVotes));
        }

        if (hasNextElement)
        {
            // PERO
            return 20 + 3;
        }

        LobbyMsgRW_PackageArrayStart(lobbyMsg, STR(clientlist));
        index = 0;
        hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < 18));
        while (hasNextElement && (index < 18))
        {
            __int64 currentClient = (__int64)&_this[index + 8 * index + 7131];
            packageOK = packageOK
                && LobbyMsgRW_PackageInt(lobbyMsg, STR(team), (__int32*)(currentClient))
                && LobbyMsgRW_PackageInt(lobbyMsg, STR(pregamepos), (__int32*)(currentClient + 4))
                && LobbyMsgRW_PackageInt(lobbyMsg, STR(pregamestate), (__int32*)(currentClient + 3))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(clvotecount), (unsigned __int32*)(currentClient + 6))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(character), (unsigned __int32*)(currentClient + 7))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(loadout), (unsigned __int32*)(currentClient + 8));

            if (!packageOK)
            {
                // bad packet
                return 7;
            }

            index++;
            hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < 18));
        }

        if (hasNextElement)
        {
            // PERO
            return 20 + 4;
        }

        packageOK = packageOK && LobbyMsgRW_PackageInt(lobbyMsg, STR(settingssize), (__int32*)(_this + 7350));

        if ((_this[7350] <= 0) || (_this[7350] > 0xC000))
        {
            // BoF attempt
            return 20 + 5;
        }

        goto PackageOK;
    }

    lobbyMode--;
    if (!lobbyMode)
    {
        goto PackageOK;
    }

    if (lobbyMode == 1)
    {
        packageOK = packageOK
            && LobbyMsgRW_PackageInt(lobbyMsg, STR(compstate), _this + 5396)
            && LobbyMsgRW_PackageInt(lobbyMsg, STR(votecount), _this + 5397);

        if (!packageOK)
        {
            // bad packet
            return 10;
        }


        __int32 numVotes = _this[5397];
        if (_this[5397] > 216)
        {
            return 20 + 7;
        }

        int index = 0;
        bool hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < numVotes));

        while (hasNextElement && (index < numVotes))
        {
            __int64 currentVote = (__int64)(&_this[8 * index + 5398]);
            packageOK = packageOK
                && LobbyMsgRW_PackageShort(lobbyMsg, STR(itemtype), (__int16*)(currentVote + 8))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(item), (unsigned int*)(currentVote + 12))
                && LobbyMsgRW_PackageShort(lobbyMsg, STR(itemgroup), (__int16*)(currentVote + 16))
                && LobbyMsgRW_PackageShort(lobbyMsg, STR(attachment), (__int16*)(currentVote + 20))
                && LobbyMsgRW_PackageShort(lobbyMsg, STR(votetype), (__int16*)(currentVote + 24))
                && LobbyMsgRW_PackageXuid(lobbyMsg, STR(votexuid), (unsigned __int64*)(currentVote));

            if (!packageOK)
            {
                return 8; // bad packet
            }

            index++;
            hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < numVotes));
        }

        if (hasNextElement)
        {
            // PERO
            return 20 + 8;
        }

        LobbyMsgRW_PackageArrayStart(lobbyMsg, STR(clientlist));
        index = 0;
        hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < 18));

        while (hasNextElement && (index < 18))
        {
            __int64 currentClient = (__int64)&_this[index + 8 * index + 7131];
            packageOK = packageOK
                && LobbyMsgRW_PackageInt(lobbyMsg, STR(team), (__int32*)(currentClient))
                && LobbyMsgRW_PackageInt(lobbyMsg, STR(pregamepos), (__int32*)(currentClient + 4))
                && LobbyMsgRW_PackageInt(lobbyMsg, STR(pregamestate), (__int32*)(currentClient + 3))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(clvotecount), (unsigned __int32*)(currentClient + 6))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(character), (unsigned __int32*)(currentClient + 7))
                && LobbyMsgRW_PackageUInt(lobbyMsg, STR(loadout), (unsigned __int32*)(currentClient + 8));

            if (!packageOK)
            {
                // bad packet
                return 9;
            }

            index++;
            hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (index < 18));
        }

        if (hasNextElement)
        {
            // PERO
            return 20 + 9;
        }

        goto PackageOK;
    }

PackageOK:

    return 0;
}

int Protection::MSG_HostHeartbeat_Inspect(char* __this, char* lobbyMsg)
{
    bool packageOK = LobbyMsgRW_PackageInt(lobbyMsg, STR(heartbeatnum), (__int32*)__this)
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(lobbytype), (__int32*)__this)
        && LobbyMsgRW_PackageInt(lobbyMsg, STR(lasthosttimems), (__int32*)__this);

    if (!packageOK) // invalid packet
    {
        return 1;
    }

    LobbyMsgRW_PackageArrayStart(lobbyMsg, STR(nomineelist));

    __int32 count = 0;
    bool hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (count < 18));
    while (hasNextElement && (count < 18))
    {
        packageOK = packageOK && LobbyMsgRW_PackageXuid(lobbyMsg, STR(xuid), (unsigned __int64*)__this);
        count++;
        hasNextElement = LobbyMsgRW_PackageElement(lobbyMsg, (count < 18));
    }

    if (hasNextElement)
    {
        return 100 + 1; // crash attempt via PERO nominee
    }

    if (!packageOK)
    {
        // bad packet
        return 2;
    }

    return 0;
}

bool Protection::CheckPendingInfoRequests(__int64 XUID, msg_t* _msg)
{
    msg_t cpyMsg;
    memcpy(&cpyMsg, _msg, sizeof(msg_t));

    unsigned int size = cpyMsg.cursize - cpyMsg.readcount;
    if (size < 2048u)
    {
        char data[2048]{};
        MSG_ReadData(&cpyMsg, data, size);

        if (!cpyMsg.overflowed)
        {
            LobbyMsg lobby_msg{};
            if (!LobbyMsgRW_PrepReadData(&lobby_msg, data, size))
            {
                //XLOG("DROP LM: FAILED TO READ DATA");
                return false;
            }

            if (lobby_msg.msgType == MESSAGE_TYPE_INFO_RESPONSE)
            {
                Msg_InfoResponse response{};
                __int32 result = MSG_InfoResponseSafe(&response, &lobby_msg);
                if (result)
                {
                    //XLOG("DROP LM: REASON %d", result);
                    return true;
                }

                dwInstantHandleLobbyMessage(XUID, 0, (char*)_msg);
                return true;
            }
            else
            {
                if (!XUID || XUID == **(__int64**)s_playerData_ptr)
                {
                    //XLOG("KEEP LM: XUID LOCAL");
                    return false;
                }

                INT64 expectedMask = 0x110000000000000;
                INT64 andMask = 0xFFFF00000000000;

                if (Protection::IsFriendsOnly)
                {
                    if ((andMask & XUID) != expectedMask)
                    {
                        //XLOG("KEEP LM: SERVER OR SPLITSCREEN");
                        return false; // server or splitscreen
                    }

                    //if (((bool(__fastcall*)(int, __int64))PTR_LiveFriends_IsFriendByXUID)(0, XUID))
                    if (IsFriendByXUIDUncached(XUID))
                    {
                        //XLOG("KEEP LM: FRIEND");
                        return false; // they are a friend! lets respond
                    }

                    //XLOG("DROP LM: UNKNOWN");
                    // not a friend, dont respond
                    return true;
                }
            }
        }
    }

    return false;
}

int Protection::MSG_InfoResponseSafe(Msg_InfoResponse* infoResponse, LobbyMsg* lm)
{
    bool packIsOK = true;
    packIsOK = LobbyMsgRW_PackageUInt(lm, "nonce", (unsigned __int32*)&infoResponse->nonce)
        && LobbyMsgRW_PackageInt(lm, "uiscreen", &infoResponse->uiScreen)
        && LobbyMsgRW_PackageUChar(lm, "nattype", &infoResponse->natType);

    if (!packIsOK)
    {
        return 1;
    }

    LobbyMsgRW_PackageArrayStart(lm, "lobbies");


    bool hasNextElement = LobbyMsgRW_PackageElement(lm, true);
    bool hasNextElement2 = false;
    for (__int32 cResponse = 0; hasNextElement && (cResponse < 2); cResponse++)
    {
        LobbyMsgRW_PackageArrayStart(lm, "lobbies");

        hasNextElement2 = LobbyMsgRW_PackageElement(lm, true);
        for (__int32 i = 0; hasNextElement2 && (i < 2); i++)
        {
            packIsOK = packIsOK && LobbyMsgRW_PackageBool(lm, "valid", &infoResponse->lobby[cResponse].isValid);

            if (!packIsOK)
            {
                return 2;
            }

            if (!infoResponse->lobby[cResponse].isValid)
            {
                hasNextElement2 = LobbyMsgRW_PackageElement(lm, (i < 2));
                continue;
            }

            packIsOK = packIsOK
                && LobbyMsgRW_PackageXuid(lm, "hostxuid", (unsigned __int64*)&infoResponse->lobby[cResponse].hostXuid)
                && LobbyMsgRW_PackageString(lm, "hostname", infoResponse->lobby[cResponse].hostName, 32)
                && LobbyMsgRW_PackageInt(lm, "networkmode", &infoResponse->lobby[cResponse].lobbyParams.networkMode)
                && LobbyMsgRW_PackageInt(lm, "mainmode", &infoResponse->lobby[cResponse].lobbyParams.mainMode)
                && LobbyMsgRW_PackageGlob(lm, "secid", (char*)&infoResponse->lobby[cResponse].secId.id, 8)
                && LobbyMsgRW_PackageGlob(lm, "seckey", infoResponse->lobby[cResponse].secKey.ab, 16)
                && LobbyMsgRW_PackageGlob(lm, "addrbuff", infoResponse->lobby[cResponse].serializedAdr.addrBuf, 37)
                && LobbyMsgRW_PackageString(lm, "ugcName", infoResponse->lobby[cResponse].ugcName, 32)
                && LobbyMsgRW_PackageUInt(lm, "ugcVersion", (unsigned __int32*)&infoResponse->lobby[cResponse].ugcVersion);

            if (!packIsOK)
            {
                return 3;
            }
            hasNextElement2 = LobbyMsgRW_PackageElement(lm, (i < 2));
        }

        if (hasNextElement2)
        {
            return 5;
        }

        hasNextElement = LobbyMsgRW_PackageElement(lm, (cResponse < 2));
    }

    if (hasNextElement || lm->msg.overflowed)
    {
        return 4;
    }

    return 0;
}

void Protection::ExceptHook(PEXCEPTION_RECORD ExceptionRecord, PCONTEXT ContextRecord)
{
    if ((INT64)ContextRecord->Rcx == 0xFFEEDDCC44332212)
    {
        InspectLM(ExceptionRecord, ContextRecord);
        ZwContinue(ContextRecord, false);
        return;
    }

    // From v2.04
    if (ExceptionRecord->ExceptionAddress == (PVOID)REBASE(0x22C965C)) // character index crash
    {
        ContextRecord->Rip = REBASE(0x22C9686);
        ZwContinue(ContextRecord, false);
        return;
    }

    // From v2.04
    if (ExceptionRecord->ExceptionAddress == (PVOID)REBASE(0x22C9676)) // character index crash
    {
        ContextRecord->Rip = REBASE(0x22C9686);
        ZwContinue(ContextRecord, false);
        return;
    }

    if (ExceptionRecord->ExceptionAddress == (PVOID)LuaCrash1)
    {
        ContextRecord->Rip = LuaCrash1Rip;
        ZwContinue(ContextRecord, false);
        return;
    }

    if (ExceptionRecord->ExceptionAddress == (PVOID)LuaCrash2)
    {
        if (!UILocalizeDefaultText)
        {
            UILocalizeDefaultText = (char*)malloc(4);
            strcpy_s(UILocalizeDefaultText, 4, "");
        }
        ContextRecord->Rdx = (INT64)UILocalizeDefaultText;
        ZwContinue(ContextRecord, false);
        return;
    }

    if (ExceptionRecord->ExceptionAddress == (PVOID)LuaCrash3)
    {
        if (!UILocalizeDefaultText)
        {
            UILocalizeDefaultText = (char*)malloc(4);
            strcpy_s(UILocalizeDefaultText, 4, "");
        }
        ContextRecord->Rsi = (INT64)UILocalizeDefaultText;
        ZwContinue(ContextRecord, false);
        return;
    }

}


namespace Iat_hook_
{
    void** find(const char* function, HMODULE module)
    {
        if (!module)
            module = GetModuleHandle(0);

        PIMAGE_DOS_HEADER img_dos_headers = (PIMAGE_DOS_HEADER)module;
        // [LOCAL] Bail out on a bad DOS header.  The old code printed a bare
        // newline as its entire "diagnostic" and then walked the header anyway,
        // using garbage offsets.
        if (img_dos_headers->e_magic != IMAGE_DOS_SIGNATURE)
            return 0;

        PIMAGE_NT_HEADERS img_nt_headers = (PIMAGE_NT_HEADERS)((BYTE*)img_dos_headers + img_dos_headers->e_lfanew);
        PIMAGE_IMPORT_DESCRIPTOR img_import_desc = (PIMAGE_IMPORT_DESCRIPTOR)((BYTE*)img_dos_headers + img_nt_headers->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);

        // PIMAGE_IMPORT_DESCRIPTOR rather than IMAGE_IMPORT_DESCRIPTOR*: the
        // former carries the __unaligned qualifier winnt.h puts on it, so the
        // initialisation no longer trips C4090 (the old spelling did).
        for (PIMAGE_IMPORT_DESCRIPTOR iid = img_import_desc; iid->Name != 0; iid++) {
            // [LOCAL] OriginalFirstThunk == 0 marks a BOUND import: there is no
            // name table at all, and the old code still read "module + 2" as if
            // there were one.
            if (iid->OriginalFirstThunk == 0)
                continue;

            auto* firstThunk = (IMAGE_THUNK_DATA*)((BYTE*)module + iid->FirstThunk);
            auto* nameThunk = (IMAGE_THUNK_DATA*)((BYTE*)module + iid->OriginalFirstThunk);

            for (int func_idx = 0; firstThunk[func_idx].u1.Function != 0; func_idx++) {
                // [LOCAL] A name-table entry is either an ordinal (high bit set,
                // no name) or an RVA to an IMAGE_IMPORT_BY_NAME.  The old code
                // dereferenced both as names; the "nmod_func_name >= 0" check
                // meant to filter them out is always true for a user-mode
                // pointer.
                if (nameThunk[func_idx].u1.Ordinal & IMAGE_ORDINAL_FLAG64)
                    continue;

                auto* importByName = (IMAGE_IMPORT_BY_NAME*)((BYTE*)module + nameThunk[func_idx].u1.AddressOfData);
                if (!::strcmp(function, (const char*)importByName->Name))
                    return (void**)&firstThunk[func_idx].u1.Function;
            }
        }

        return 0;

    }

    uintptr_t detour_iat_ptr(const char* function, void* newfunction, HMODULE module)
    {
        void** func_ptr = find(function, module);
        // [LOCAL] find() returns 0 when the module does not import that symbol
        // at all.  Dereferencing it here was an immediate access violation
        // inside install() / uninstall().
        if (!func_ptr)
            return 0;

        if (*func_ptr == newfunction || *func_ptr == nullptr)
            return 0;

        DWORD old_rights, new_rights = PAGE_READWRITE;
        VirtualProtect(func_ptr, sizeof(uintptr_t), new_rights, &old_rights);
        uintptr_t ret = (uintptr_t)*func_ptr;
        *func_ptr = newfunction;
        VirtualProtect(func_ptr, sizeof(uintptr_t), old_rights, &new_rights);
        return ret;
    }
};
