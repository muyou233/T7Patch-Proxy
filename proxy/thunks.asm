; =====================================================================
;  proxy/thunks.asm
; ---------------------------------------------------------------------
;  x64 export forwarders for the d3d11.dll proxy used by T7Patch.
;
;  Black Ops III ships with a *static* import of d3d11.dll, so this
;  module is loaded by the Windows loader before the game's entry point
;  runs.  Every entry point the real d3d11.dll exports has to keep
;  working, otherwise the loader (or a later LoadLibrary) fails with
;  "procedure entry point not found".
;
;  Forwarding is done with one tiny thunk per export.  A thunk is used
;  instead of a C++ function because the arguments of most d3d11 exports
;  are undocumented (D3DKMT*, D3DPerformance_*, OpenAdapter10*), and a
;  C++ wrapper would have to know every signature exactly.  A plain
;  jump keeps RCX/RDX/R8/R9, XMM0-XMM3 and the stack arguments of the
;  original caller completely untouched.
;
;  RAX is used as the scratch register.  It is volatile under the x64
;  ABI and never carries an argument, so clobbering it is safe.
;
;  Do not add EXPORT directives here - the export table is owned by
;  proxy/d3d11.def.
; =====================================================================

.data

; One slot per d3d11 export, indexed by the *ordinal* the real d3d11.dll
; uses.  Filled in at run time by ProxyResolveExports() in Proxy.cpp.
; Keep the size in sync with kExportCount in Proxy.cpp.
PUBLIC g_d3d11Targets
g_d3d11Targets QWORD 51 DUP (0)

.code

; ---------------------------------------------------------------------
;  mkthunk <export name>, <ordinal>
;
;  Emits a PUBLIC leaf routine that tail-jumps to whatever address was
;  stored in g_d3d11Targets[ordinal].
; ---------------------------------------------------------------------
mkthunk MACRO nm:REQ, idx:REQ
PUBLIC nm
nm PROC
    mov rax, QWORD PTR [g_d3d11Targets + idx * 8]
    jmp rax
nm ENDP
ENDM

;                              ordinal
mkthunk D3D11CreateDeviceForD3D12,                  0
mkthunk D3DKMTCloseAdapter,                         1
mkthunk D3DKMTDestroyAllocation,                    2
mkthunk D3DKMTDestroyContext,                       3
mkthunk D3DKMTDestroyDevice,                        4
mkthunk D3DKMTDestroySynchronizationObject,         5
mkthunk D3DKMTPresent,                              6
mkthunk D3DKMTQueryAdapterInfo,                     7
mkthunk D3DKMTSetDisplayPrivateDriverFormat,        8
mkthunk D3DKMTSignalSynchronizationObject,          9
mkthunk D3DKMTUnlock,                              10
mkthunk D3DKMTWaitForSynchronizationObject,        11
mkthunk EnableFeatureLevelUpgrade,                 12
mkthunk OpenAdapter10,                             13
mkthunk OpenAdapter10_2,                           14
mkthunk CreateDirect3D11DeviceFromDXGIDevice,      15
mkthunk CreateDirect3D11SurfaceFromDXGISurface,    16
mkthunk D3D11CoreCreateDevice,                     17
mkthunk D3D11CoreCreateLayeredDevice,              18
mkthunk D3D11CoreGetLayeredDeviceSize,             19
mkthunk D3D11CoreRegisterLayers,                   20
; 21 = D3D11CreateDevice               -> Proxy.cpp
; 22 = D3D11CreateDeviceAndSwapChain   -> Proxy.cpp
mkthunk D3D11On12CreateDevice,                     23
mkthunk D3DKMTCreateAllocation,                    24
mkthunk D3DKMTCreateContext,                       25
mkthunk D3DKMTCreateDevice,                        26
mkthunk D3DKMTCreateSynchronizationObject,         27
mkthunk D3DKMTEscape,                              28
mkthunk D3DKMTGetContextSchedulingPriority,        29
mkthunk D3DKMTGetDeviceState,                      30
mkthunk D3DKMTGetDisplayModeList,                  31
mkthunk D3DKMTGetMultisampleMethodList,            32
mkthunk D3DKMTGetRuntimeData,                      33
mkthunk D3DKMTGetSharedPrimaryHandle,              34
mkthunk D3DKMTLock,                                35
mkthunk D3DKMTOpenAdapterFromHdc,                  36
mkthunk D3DKMTOpenResource,                        37
mkthunk D3DKMTQueryAllocationResidency,            38
mkthunk D3DKMTQueryResourceInfo,                   39
mkthunk D3DKMTRender,                              40
mkthunk D3DKMTSetAllocationPriority,               41
mkthunk D3DKMTSetContextSchedulingPriority,        42
mkthunk D3DKMTSetDisplayMode,                      43
mkthunk D3DKMTSetGammaRamp,                        44
mkthunk D3DKMTSetVidPnSourceOwner,                 45
mkthunk D3DKMTWaitForVerticalBlankEvent,           46
mkthunk D3DPerformance_BeginEvent,                 47
mkthunk D3DPerformance_EndEvent,                   48
mkthunk D3DPerformance_GetStatus,                  49
mkthunk D3DPerformance_SetMarker,                  50

END
