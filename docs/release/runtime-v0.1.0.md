# Historical runtime evidence

These records describe the v0.1.0 preparation work.
The [original report](archive/v0.1.0/runtime-v0.1.0.md) retains the implementation details.
Use [third-party notices](../../third_party/README.md) for current bundle instructions.
Use the [user guide](../user-guide.md) for current operating instructions.

## Logs and diagnostics: #17 and PR #112

Default logs used fixed event, stage, and error codes.
The worker drained child stderr through pipes and suppressed its content.
Interactive startup could display access details.
Non-interactive startup did not call `access show`.

The historical report recorded 134 passing focused tests.
This count does not describe the current test suite.
Explicit diagnostic commands can display private installation data.

## Native media runtime

The image built PyAV from source against FFmpeg 8.1.2 without external GPL codecs.
The system FFmpeg CLI remained a separate program for media normalization.
Media checks decoded samples with TorchCodec and PyAV.
They checked loaded library paths through `/proc/self/maps`.

TorchCodec 0.11.1 used the PyPI wheel on amd64.
The arm64 build used the official `0.11.1+cu128` wheel.
Torch and Torchaudio used CUDA 12.8.
These versions identify the historical configuration.

The build replaced embedded GNU runtime libraries with Ubuntu runtime libraries.
It checked exported symbols before replacement.
The image retained hashes and package sources in `openmp-runtime.json`.
Platform checks covered native objects, notices, and the Tokenizers Rust manifest.
Corresponding source and build recipes accompanied the release bundle.

Historical timings do not establish performance for a changed native runtime.
Each new image needs the artifact checks in the [release process](process.md).
The [checked-in inventory](runtime-inventory-amd64.json) identifies its original local artifact only.
