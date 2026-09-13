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

}
