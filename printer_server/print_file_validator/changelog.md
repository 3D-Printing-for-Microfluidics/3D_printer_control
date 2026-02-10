## v5.0.0 (2026-01-16) — v4 → v5 Schema Transition

### Summary
- ✨ New: Added `Named layer groups` and the ability to reference them from `Layers[]`.
- ✨ New: Added explicit special techniques for layers and exposures (force squeeze, 0 um layer duplication, print on film).
- 💥 Breaking: Moved vacuum control from `Header->Print under vacuum` to `Special print techniques->Print under vacuum`.
- 💥 Breaking: Moved squeeze force from `Position Settings` to `Position settings->Special layer techniques->Squeeze out resin`.
- 💥 Breaking: Removed `Templates` (use `Named layer groups` and `Using named layer group` instead).
- 💥 Breaking: Print on Film techniques now must use special techniques. Negative layers are no longer allowed.
- 💥 Breaking: `Light engine` is required in default image settings.
- 💥 Breaking: Moved wavelength from `Light engine` to dedicated `Light engine wavelength (nm)`.
- 💥 Breaking: Removed `Do dark grayscale correction` and renamed `Do light grayscale correction` to `Do grayscale correction`.

### Details
- Fully expanded named layer groups:
	- `Named layer groups`
		- `Comment` (string, optional)
		- `<Group name>` (array of layers)
			- Each item is a standard layer object
	- `Layers[]` can include a named group reference object:
		- `Using named layer group` (string, required)
		- `Number of duplications` (integer, optional)
		- `Variables` (object, optional; overrides global variables for this group instance)
		- `Comment` (string, optional)
- Added `Special print techniques` at the top level, and `Special layer techniques` / `Special image techniques` within layers and image settings.
- Fully expanded special techniques:
	- `Special print techniques.Print under vacuum`
		- `Enable vacuum` (boolean, default false)
		- `Target vacuum level (Torr)` (number, default 10)
		- `Vacuum wait time (sec)` (number, default 0)
	- `Position settings.Special layer techniques.Squeeze out resin`
		- `Enable squeeze` (boolean, default false)
		- `Squeeze count` (integer, default 0)
		- `Squeeze force (N)` (number, default 40)
		- `Squeeze time (ms)` (number, default 100)
	- `Image settings.Special image techniques.0 um layer`
		- `Enable 0 um layer` (boolean, default false)
		- `Number of duplications` (integer, default 1)
	- `Image settings.Special image techniques.Print on film`
		- `Enable print on film` (boolean, default false)
		- `Distance up (mm)` (number, default 0.3)

### Technical changes
- Standardized shared fields through `$defs/COMMON_PROPS` and referenced them across the schema.
- Tightened `Variables` to allow only `string | number | boolean` values (previously unconstrained).
- Changed `Squeeze count` to an integer.
- Relaxed `Light engine` to a free string (removed enum constraint).
- Added `Distance up (mm)` at the layer base to support technique-specific overrides.
- Added optional `Comment` fields to more sections (e.g., named settings and layer groups) for metadata consistency.
