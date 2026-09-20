#pragma once

// [LOCAL] Resource id for the dictionary that ships inside the dll.
//
// Shared between the resource script (translate_default.rc) and translate.cpp
// so the two can never drift apart.  Keep it in the 101..199 range: 1..100 is
// where a compiler-generated version resource would live.
#define IDR_TRANSLATE_DICT 101

// [LOCAL] 2026-09-20: the pinyin table ships inside the dll the same way.  It
// is a fixed 6763-character GB2312 set plus the multi-pronunciation phrases -
// data that does not really want to be updated, so "nothing to copy next to
// d3d11.dll" is worth more than the update channel here.  The external file
// still wins whenever it exists, so hot-reloading a fix stays possible.
#define IDR_TRANSLATE_PINYIN 102
