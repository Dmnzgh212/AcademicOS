# Local natural sorting — localized module candidate

Useful behavior: sort entered course-material/file labels as Lecture 1, Lecture 2,
Lecture 10 instead of lexical 1, 10, 2. This module receives only labels explicitly
entered by the user; it never enumerates or opens files and has no network/storage
permission. All computation executes in core Wasm via lifehub.service-json@1.
It is a separate one-shot package, not a background service or a calendar feature.

Original C algorithm: Martin Pool/sourcefrog natsort, pinned commit
cdd8df9602e727482ae5e051cff74b7ec7ffa07a, Zlib license. See NOTICE.md and retained
source headers. Locale calls were replaced with fixed ASCII classification; the
LifeHub adapter supplies bounded array IO and stable insertion sort. No Core edits.
Zig 0.13.0 is an engineering build dependency only, not a platform runtime dependency.
No compiler or PersonIR research was introduced. Tiny JSON glue deliberately accepts
only an array of printable ASCII labels (32 labels / 128 chars each), preserving
escaped quote/backslash spelling. Unicode and control characters fail closed.

## Engineering preparation

With a matching installed LifeHub wheel, Wasmtime 36, pytest and Zig 0.13.0:

```sh
python -m pip install ziglang==0.13.0
python ecosystem/local-natural-sort/build.py /fresh/path/packages
python -m pytest -q ecosystem/local-natural-sort/test_module.py
python -I ecosystem/local-natural-sort/verify.py /fresh/path/packages
```

verify.py is an engineering synthetic-data smoke; its automatic approvals apply
only to the built fixtures and disposable storage. It covers installation, pregrant
denial, actual useful output, revoke denial and reinstall not reviving grants.

## Operator walkthrough

Engineers supply the two reviewed .lhpkg files, operator.py and matching Python/
LifeHub environment. Users do not compile C/Wasm or audit the source. This is still
a Python CLI prototype, not an installer or a delivered one-click consumer product.
In that prepared environment (replace package/workspace paths with supplied locations):

```sh
python operator.py import --packages packages --workspace my-sort
python operator.py enable --workspace my-sort
python operator.py sort "Lecture 10.pdf" "Lecture 2.pdf" "Lecture 1.pdf" --workspace my-sort
python operator.py disable --workspace my-sort
python operator.py remove --workspace my-sort
```

Import and enable are separate confirmations; installation never implies authority.
Reject by answering anything other than yes. The next sort fails after disable.
This service finishes each call, so there is no background process to stop; disable
removes future call authority and remove uninstalls packages. Reinstallation needs
new authorization. The Shell uses documented CLI contracts and never reads internal
storage directly. Copy only LHSORT_* diagnostic codes; private labels and raw host
tracebacks are excluded from emitted errors. Labels remain in user output and the
transient request file during a call; no secure deletion guarantee is claimed.

## Boundaries and maintenance

The compiler-produced reserved one-entry table is stripped only if its exact known
shape matches; Wasmtime validates the resulting module, rejecting referenced or
unexpected tables. Module memory is fixed at 2 MiB and host fuel/IO bounds remain.
No broad filesystem access, effects or egress. Uppercase sorting remains upstream
case-sensitive behavior; this is not locale/Unicode collation or general JSON parsing.
Check changes against upstream and license before updates, rerun adversarial inputs,
rebuild reviewed package hashes and revoke/reinstall tests. No auto-update path.

M1/merge acceptance is separate. This practical module candidate supplies a localized
application function; it is not proof of a mature ecosystem or full user delivery.
