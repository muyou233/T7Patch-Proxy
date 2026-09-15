#pragma once

// [LOCAL] Resource id for the dictionary that ships inside the dll.
//
// Shared between the resource script (translate_default.rc) and translate.cpp
// so the two can never drift apart.  Keep it in the 101..199 range: 1..100 is
// where a compiler-generated version resource would live.
#define IDR_TRANSLATE_DICT 101
