# linkShortcutFileFormat
Cross-platform file format support for windows .lnk shortcut files.

It achieves cross-platform support by not relying on windows .dll libraries,
but instead works with the binary .lnk file directly.

## Limitations

Aspects of [MS-SHLLINK] that are not (fully) handled:

- **LinkTargetIDList**: kept as raw bytes and split into items (`idListItems`), but item contents are not interpreted. Without a LinkInfo section, the target is only guessed from the 8.3 names of file/folder items. Unicode names, extension blocks and non-filesystem items (control panel, virtual folders) are not decoded.
- **Saving**: strings are always written as unicode and LinkInfo is rebuilt from `targetPath`, so the original LinkInfo layout and any volume details beyond drive type, serial number and label are not preserved.
- **LinkInfo**: the unicode path variants are preferred when reading and never cross-checked against the ANSI ones. ANSI strings use the system code page (`mbcs` on Windows, `cp1252` elsewhere), so unrepresentable characters become `?`.
- **Header**: the reserved fields are not read and are always written as zero. `ShowCommand`, hotkey and flag values are stored as-is without validation.
- **ExtraData**:
  - `PropertyStoreDataBlock` and `VistaAndAboveIDListDataBlock` are exposed only as raw bytes (no [MS-PROPSTORE] parsing).
  - `KnownFolderDataBlock` and `SpecialFolderDataBlock` are read, but the folder is never resolved to a path.
  - Blocks with unknown signatures are preserved but not interpreted; malformed block sizes are rejected, but the block-specific body sizes are not validated.
  - Icon environment, Darwin, shim and tracker blocks are read and written but not acted on: installer IDs are not resolved, and moved targets are not searched for.
- **Flags without behavior**: `RunAsUser`, `RunInSeparateProcess`, `ForceNoLinkTrack`, `AllowLinkToLink` and similar flags are exposed but do not affect target resolution.
- **Environment paths**: `EnvironmentVariableDataBlock` targets are expanded using the current process environment, and `PreferEnvironmentPath` is honored. Unknown variables remain unchanged; icon environment paths are still exposed raw.
- **Platform**: icon extraction needs Windows and `pywin32`; elsewhere only the binary format is available.
