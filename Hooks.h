#pragma once
#include "framework.h"

namespace hooks {

	extern void ApplyVMTHooks();
	extern void ApplyMemoryPatches();
	extern void ApplyHooks();
	extern void DestroyHooks();

	// [LOCAL] Blocks in-process loading of the legacy d3dcompiler_46.dll so the
	// engine falls back to the modern D3DCompiler_47 shader pipeline.
	// Fixes the map-load / first-effect hitching caused by realtime HLSL
	// compilation through the old runtime compiler.  (User-verified fix.)
	extern void InstallD3DCompilerBlock();

	// [LOCAL] Runtime toggle for the overlay menu.  The hook is created once
	// at startup; these flip whether calls land in it (MinHook enable/disable,
	// no re-hooking).  SetD3DCompilerBlock also keeps t7patch.conf in sync.
	extern void SetD3DCompilerBlock(bool enable);
	extern bool IsD3DCompilerBlockEnabled();
	extern int  GetD3DCompilerBlockCount(); // interceptions this session

}
