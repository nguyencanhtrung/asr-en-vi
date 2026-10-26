# Third-party notices and corresponding source

The application license applies to the application code. Dependencies retain
their own licenses. NVIDIA portions of the container are provided subject to
[the NVIDIA container terms](notices/nvidia/base-image/NGC-DL-CONTAINER-LICENSE)
and the package-specific terms retained in the image. Intel oneMKL retains its
[unmodified redistribution terms](notices/native/oneMKL/2025.3.0/LICENSE.txt).

The notice tree is copied to `/usr/local/share/licenses/asr-en-vi/third-party/`.
System copyright files remain in `/usr/share/doc`; OMP notices remain in
`/usr/local/share/licenses/omp/`. The English application license is authoritative;
`LICENSE.vi` is a reference translation.

For each loaded platform image, run:

```sh
python3 scripts/prepare-release-bundle.py IMAGE --version 0.1.0 --output /tmp/release-sources
```

This checks the image version and GNU runtime replacements, inventories installed
packages, downloads exact corresponding source and creates an archive plus
SHA-256. Collection failures stop publication. The tag workflow uploads the
archive to the public GitHub Release before publishing that platform image.
Archive names include platform and image configuration digest; keep older
archives available when rebuilding an existing version.

`bundle-spec.json` pins additional upstream notices and source archives.
`NOTICE-MANIFEST.json` and `SOURCE-MANIFEST.json` are collection evidence, not
blanket legal approval. The large source archives stay outside the repository.
The checked-in inventory describes the labeled local validation image; regenerate
it for each actual platform artifact. CUDA toolkit copyright mentions CUDA-GDB,
which is absent from this runtime; exact package/version/copyright exclusions
are recorded, and the publication check rejects an image containing CUDA-GDB.
