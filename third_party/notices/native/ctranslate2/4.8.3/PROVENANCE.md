# CTranslate2 4.8.3 native provenance

Evidence is for the exact Linux CPython 3.12 wheel:

- wheel SHA-256: `7e161eb031fcf2a5d81ce3a1cd8be4954c7df758d96cfaba57aeecc69a0c00ae`
- `libctranslate2-bdb19cbc.so.4.8.3` SHA-256: `9a28d257e726d2a3db337fa5e10f31cd190975955f6b3a9bb01801eb2f1e6975`
- bundled `libgomp-e985bcbb.so.1.0.0` SHA-256: `a43904e4fa297301d4640dc1bb3c8a3480b406f99e498eba9b1914b68aab604a`
- CTranslate2 v4.8.3 source archive SHA-256:
  `255009e3f25808e67d4c3500fd69e74076d814a62784eaf544b39fc5a472bcd9`

The native object has a `NEEDED` entry for the bundled `libgomp` and embeds
oneDNN 3.1.1 paths/symbols and oneMKL symbols. The oneDNN source archive and
`THIRD-PARTY-PROGRAMS` file are collected with their hashes in the generated
notice/source manifests. The public Intel oneAPI license overview PDF is also
collected, but the exact Intel oneMKL 2025.3.0 build inputs and third-party
materials used to produce this wheel are not established by the public
CTranslate2 source archive.

The CTranslate2 release submodule inputs are pinned and downloaded by the
collector: `cpu_features` `8a494eb1e158ec2050e5f699a504fbc9b896a43b`,
`cutlass` `bbe579a9e3beb6ea6626d9227ec32d0dae119a49`, `cxxopts`
`44380e5a44706ab7347f400698c703eb2a196202`, `googletest`
`f8d7d77c06936315286eb55f8de22cd23c188571`, `ruy`
`363f252289fb7a1fba1703d99196524698cb884d`, `spdlog`
`76fb40d95455f249bd70824ecfcae7a8f0930fa3`, and `thrust`/CCCL
`b5fe509fd11a925f90d6495176707cc1184eed9d`.

## Scoped GPL/runtime-exception finding

This is not an automatic blocker for every GPL identifier in the native
payload. The official [GCC Runtime Library Exception 3.1](https://www.gnu.org/licenses/gcc-exception-3.1.en.html)
permits a work of Target Code formed by combining the covered Runtime Library
with Independent Modules to be conveyed under chosen terms when the Target
Code was produced by Eligible Compilation Processes. The [official FAQ](https://www.gnu.org/licenses/gcc-exception-3.1-faq.html.en)
also distinguishes that combined-work permission from distribution of the GCC
runtime itself as an independent object-code library: that independent library
still follows the GPL source method.

The wheel contains `libgomp` as a separate ELF shared object, with a distinct
SONAME and a `NEEDED` relationship from CTranslate2. The finding below is
therefore limited to the corresponding source or valid written-source offer
for that separately shipped object. It does not classify CTranslate2's
combined Target Code as GPL merely because its native object references
`libgomp`, and it does not treat the presence of a GPL expression alone as
proof that the application's source must be published.

The release container replaces the separately shipped wheel OpenMP object with
Ubuntu `libgomp1` before copying the virtual environment to the runtime layer.
`openmp-runtime.json` records original and replacement hashes. The publication
check compares the actual CTranslate2 copy with the installed system library.
The corresponding Ubuntu GCC source package is collected with the release.
The dependency filename remains unchanged; the build checks CTranslate2 import
and CPU compute types. Historical performance measurements do not establish
performance of this replacement. The upstream wheel downloaded by direct pip
installation is a separate upstream artifact.

## ARM64 wheel and recipe evidence

The ARM64 native inventory is recorded in
`third_party/platform-coverage.json`; it is checked against the installed
distribution files before a platform image can be published. The captured
wheel hashes are:

- CTranslate2 4.8.3: `1b9ff80ed67ce7974cb0eafdf7ad79407678b5bea70db934c0d20aaa9db57964`
- tokenizers 0.23.3: `ec82e80e65a862275b97c3d90b7a523df8d9519ee48aeb4e9625b2cc909274e0`
- torch 2.11.0+cu128: `9c8f38efee365cb9d334de8a83ce52fc7e5fc9e5a7b0853285efa1b69e00b0f2`
- torchaudio 2.11.0+cu128: `d055c9ca9d4f0ffcbaa0fc22138bafd675256de392bdaadde00d797faa90ca56`
- torchcodec 0.11.1+cu128: `2f1efd182a3728d3a858382f973afabd144f66bfb5c1d5a72c504692cf73a65b`

The official CTranslate2 v4.8.3 ARM build recipe is retained as
`ctranslate2-build-recipe.sh` in the corresponding-source evidence. Its
SHA-256 is
`e075680b5730c2ebdfe0c0b3eb07cbcd4dfcb5a3ea1a6d31253d30a7291c1ced`.
It pins OpenBLAS `0.3.26` with `TARGET=ARMV8`, `NO_SHARED=1`,
`BUILD_SINGLE=1`, `NO_LAPACK=1`, `ONLY_CBLAS=1`, and `USE_OPENMP=1`, and
builds CTranslate2 with `WITH_OPENBLAS=ON` and `WITH_RUY=ON`. The copied
OpenBLAS license hash is
`190b5a9c8d9723fe958ad33916bd7346d96fab3c5ea90832bb02d854f620fcff`; the
ruy license at commit `363f252289fb7a1fba1703d99196524698cb884d` hashes to
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.

The tokenizers Rust SBOM is also architecture-bound rather than assumed to be
identical: the amd64 wheel SBOM hashes to
`6faa23324b2b53b4a8da9b451a675610cc45e1a23e8c5bb0740c080064e1ba0d`, while
the ARM64 wheel SBOM hashes to
`950788cf8d0bd531aac28fbc58cbbe7297a743115c5310dbd8371d4d95bf5be5`.
Both contain 127 component PURLs with set digest
`eb2b373744b60adac9da4a6d51254d36df883d278d27c6544b6dbdac47bc59c0`;
the platform gate checks that set against the checked-in Rust manifest and
all 127 component notice hashes.
