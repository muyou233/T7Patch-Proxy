#pragma once

#define WIN32_LEAN_AND_MEAN
#include <ctype.h>
#include <iostream>
#include <Winternl.h>
#include <unordered_set>
#include <filesystem>
#include "functional"
#include "Arxan.h"
#include <unordered_map>
#include <fstream>
#include <sstream>
#include <windows.h>
#include <intrin.h>
#include <cstdint>
#include <cstddef>
#include <TlHelp32.h>
#include "structs.h"
#include "minhook/include/MinHook.h"
#include "gscu_hashing.h"
#include "offsets.h"
#include "Protection.h"
#include "Hooks.h"

constexpr uint32_t fnv_base_32 = 0x4B9ACE2F;

inline uint32_t fnv1a(const char* key) {

	const char* data = key;
	uint32_t hash = 0x4B9ACE2F;
	while (*data)
	{
		hash ^= *data;
		hash *= 0x1000193;
		data++;
	}
	hash *= 0x1000193; // bo3 wtf lol
	return hash;

}

template <unsigned __int32 NUM>
struct canon_const_builtins
{
	static const unsigned __int32 value = NUM;
};

constexpr unsigned __int32 fnv1a_const(const char* input)
{
	const char* data = input;
	uint32_t hash = 0x4B9ACE2F;
	while (*data)
	{
		hash ^= *data;
		hash *= 0x01000193;
		data++;
	}
	hash *= 0x01000193; // bo3 wtf lol
	return hash;
}

#define FNV32(x) canon_const_builtins<fnv1a_const(x)>::value

inline bool is_in_array(std::string cmp1, std::vector<std::string> cmp2)
{
	for (auto& cmp : cmp2)
	{
		if (!strcmp(cmp1.data(), cmp.data()))
			return true;
	}
	return false;
}

inline bool is_in_number_array(int cmp1, std::vector<int> cmp2)
{
	for (auto cmp : cmp2)
	{
		if (cmp1 == cmp)
			return true;
	}
	return false;
}

inline std::string to_lower(std::string text)
{
	std::transform(text.begin(), text.end(), text.begin(), ::tolower);
	return text;
}

inline bool is_equal(const std::string& lhs, const std::string& rhs, const std::size_t count, const bool case_sensitive)
{
	auto left = lhs;
	auto right = rhs;

	if (count != std::string::npos)
	{
		if (lhs.size() > count)
			left.erase(count);

		if (rhs.size() > count)
			right.erase(count);
	}

	if (case_sensitive)
	{
		return left == right;
	}

	else
	{
		return to_lower(left) == to_lower(right);
	}
}

inline bool is_address_within_range(std::uintptr_t address, std::uintptr_t min, std::uintptr_t max)
{
	return (address >= min && address <= max);
}

inline std::vector<std::string> legit_packets = {
	"connectResponse",
	"statresponse",
	"LM",
	"disconnect",
	"loadoutResponse",
	"infoResponse",
	"statusResponse",
	"keyAuthorize",
	"error",
	"print",
	"fastrestart",
	"ping",
	"pinga",
	"steamAuthReq",
	"cfl"
};

// [LOCAL] Generated files now live in a "T7Patch" subfolder instead of being
// dropped straight into the game directory.
//
// The paths stay relative on purpose.  Steam starts the game with its working
// directory set to the game folder, and the crash log is written from an
// exception handler that must not depend on anything heavier than fopen().
#define T7PATCH_DATA_DIR "T7Patch"
#define CRASH_LOG_NAME T7PATCH_DATA_DIR "\\crashes.log"
#define PATCH_CONFIG_LOCATION T7PATCH_DATA_DIR "\\t7patch.conf"

// Creates that folder once, on first use.  Idempotent, and safe to call from
// DllMain - CreateDirectoryA does not touch the loader lock.
inline void t7patch_ensure_data_dir()
{
    static const int created = []() -> int
    {
        return (CreateDirectoryA(T7PATCH_DATA_DIR, nullptr) ||
                GetLastError() == ERROR_ALREADY_EXISTS) ? 1 : 0;
    }();
    (void)created;
}

// [LOCAL] Config helpers (implemented in Protection.cpp).
// t7patch_load_config_early() reads t7patch.conf without touching the engine,
// so it is safe from the DllMain-era thread that arms the 46 block; the getter
// exposes the block_d3dcompiler46 switch (default: disabled).  Both are used
// because the block is installed long before the normal settings path runs.
void t7patch_load_config_early();
bool t7patch_block_d3dcompiler46_enabled();
int t7patch_menu_key();          // virtual-key code that toggles the overlay (default VK_INSERT)
int t7patch_cfg_menu_lang();     // overlay language: 1 = Chinese (default), 0 = English
void t7patch_cfg_set_menu_lang(int value);
// [LOCAL] UI translation layer (src/translate.cpp): replace English UI text with
// the dictionary in T7Patch\translate_zh.txt; the second switch collects the
// distinct English strings into T7Patch\ui_dump.txt for building it.
bool t7patch_cfg_translate_enabled();
void t7patch_cfg_set_translate(int enabled);
void t7patch_cfg_block_translate(int blocked); // start-up language gate latch (Protection.cpp)
void t7patch_cfg_persist_translate_off();     // ask load_settings_initial() to write that decision down
bool t7patch_cfg_dump_ui_strings();
void t7patch_cfg_set_menu_key(int vk);
bool t7patch_menu_auto_open();   // 1 = overlay opens automatically at game start
void t7patch_cfg_set_menu_auto_open(bool v); // menu-side auto-open switch
void t7patch_config_set_block46(bool enable); // menu-side 46 switch (memory)
// [LOCAL] The 46 opt-out's FILE layer (Protection.cpp).  The switch renames
// <game>\d3dcompiler_46.dll to d3dcompiler_46.dll.bak and back, so the engine
// cannot find the legacy compiler at all - see the comment there for why a
// rename replaced the old LoadLibraryExW hook.  state: 0 = .dll present,
// 1 = only .bak, 2 = neither, 3 = both.
int  t7patch_d3dcompiler46_file_state();
bool t7patch_d3dcompiler46_hide_file(bool hide);
void t7patch_d3dcompiler46_reconcile();
void t7patch_config_save();                   // persist config + apply live settings
// [LOCAL] Field accessors for the overlay menu's settings panel.
void t7patch_cfg_playername(char* dst, size_t dstSize); // [LOCAL] copies under the config lock (dstSize 16)
const char* t7patch_game_playername(); // game's own current name (menu fallback)
void t7patch_cfg_set_playername(const char* v);
bool t7patch_cfg_friends_only();
void t7patch_cfg_set_friends_only(bool v);
void t7patch_cfg_network_password(char* dst, size_t dstSize); // [LOCAL] copies under the config lock (dstSize 1024)
void t7patch_cfg_set_network_password(const char* v);
// [LOCAL] Start-up failure notice (dllmain.cpp).  Called when T7 Patch refuses
// to run in this executable: the BlackOps3.exe build is not one of the
// profiles in GameBuild.h, or the Arxan anti-tamper bypass could not be set
// up.  Both used to be silent - a patch that does nothing looks exactly like a
// broken install.  The dialog is shown from its own thread (the callable
// zbr_run_gamemode_lui export runs on a game thread and must not block), at
// most once per process, and never in a process that is not the game.
// reason is a short ASCII diagnostic; it is ASCII because every caller passes
// one of the engine-side literals.
void t7patch_warn_startup_failure(const char* reason);

#define ZBR_WINDOW_TEXT "Call of Duty: Black Ops III (community patch by serious)"
// [LOCAL] display string trimmed to just the version (was "Patch 3.06 - by serious <3")
// [LOCAL] Split so the overlay title can say "T7Patch <ver>" while the game
// window text keeps "Patch <ver>" - bump ZBR_VERSION only.
#define ZBR_VERSION "3.08"
#define ZBR_VERSION_FULL "Patch " ZBR_VERSION
#define SPOOF_UNLOCK_ALL false
#define SPOOF_SKIP_CWL false
#define SPOOF_GUM_COUNT 255
