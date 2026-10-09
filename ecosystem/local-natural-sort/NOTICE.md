# Localized natural sorting

Original algorithm: Martin Pool, sourcefrog/natsort, Zlib license.
Pinned upstream commit: cdd8df9602e727482ae5e051cff74b7ec7ffa07a.
https://github.com/sourcefrog/natsort/tree/cdd8df9602e727482ae5e051cff74b7ec7ffa07a

The upstream license and copyright remain in vendor/strnatcmp.c and .h.
LifeHub modifications: replace locale/ctype calls with fixed ASCII classification;
add bounded label-list JSON glue and stable merge sorting, compile with Zig 0.13.0 into
core Wasm without libc/WASI. The reserved unreferenced compiler table is removed
and resulting module validated by Wasmtime; no host table limit is widened.
This is not the unmodified upstream distribution and not an original LifeHub algorithm.

Module input/output only: up to 16 printable ASCII labels, each up to 64 bytes.
No filesystem, network, storage or effect permissions; the independent Shell may
invoke the sort service only after an explicit host-mediated service grant.
No Unicode collation, locale sorting, credential/data collection or automatic updates.

Update responsibility: project engineers review upstream changes, retain license,
reapply marked ASCII alteration, rebuild/retest before distribution. This review
establishes provenance, not a comprehensive security audit of upstream/compiler.

/* -*- mode: c; c-file-style: "k&r" -*-

  strnatcmp.c -- Perform 'natural order' comparisons of strings in C.
  Copyright (C) 2000, 2004 by Martin Pool <mbp sourcefrog net>

  This software is provided 'as-is', without any express or implied
  warranty.  In no event will the authors be held liable for any damages
  arising from the use of this software.

  Permission is granted to anyone to use this software for any purpose,
  including commercial applications, and to alter it and redistribute it
  freely, subject to the following restrictions:

  1. The origin of this software must not be misrepresented; you must not
     claim that you wrote the original software. If you use this software
     in a product, an acknowledgment in the product documentation would be
     appreciated but is not required.
  2. Altered source versions must be plainly marked as such, and must not be
     misrepresented as being the original software.
  3. This notice may not be removed or altered from any source distribution.
*/

