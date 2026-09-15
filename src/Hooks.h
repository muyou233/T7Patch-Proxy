#pragma once
#include "framework.h"

namespace hooks {

	extern void ApplyVMTHooks();
	extern void ApplyMemoryPatches();
	extern void ApplyHooks();
	extern void DestroyHooks();

	// [LOCAL] Fallback layer of the legacy d3dcompiler_46 opt-out: refuses
	// in-process loads of that module.  The primary mechanism is the FILE MOVE
	// in Protection.cpp (t7patch_d3dcompiler46_*); this hook only covers what
	// a move cannot - a read-only game folder, or the file being put back by
	// hand while the game runs.  It never fired once across four measured
	// sessions (2026-09-15); see the note in Hooks.cpp.
	extern void InstallD3DCompilerBlock();

	// [LOCAL] Menu toggle: moves the file (primary) and enables/disables the
	// hook (fallback), then keeps t7patch.conf in sync.
	extern void SetD3DCompilerBlock(bool enable);
	extern bool IsD3DCompilerBlockEnabled(); // the SETTING, not the hook state
	extern int  GetD3DCompilerBlockCount();  // hook interceptions this session

	// [LOCAL] Diagnostic switch, OFF by default: record every distinct UI-model
	// path the game touches (and LUI menu names) into the patch's log.
	extern void EnableUiModelPathLog(bool enable);

	// [LOCAL] Screen detection: true once the game rendered a MAIN MENU label
	// (mode buttons / quick-join bar).  Measured 2026-09-14: those strings are
	// resolved at render time, and never on the "press ENTER" title screen or
	// the connecting screen.  Set from the game's own thread inside the UI
	// string hooks - no polling, no cross-thread game calls.
	extern bool UiMainMenuSeen();

}
