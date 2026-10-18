# Euphoria Lab – Community Presets

Presets for **Euphoria Lab**, the GTA V ragdoll / NaturalMotion Euphoria sandbox.
The mod's **Community presets** menu reads this repository directly, so anything
merged here shows up in-game for everyone.

## Preset types

| Type | Folder | What it holds |
|------|--------|---------------|
| Stack | `presets/stack/` | A Euphoria behaviour stack (starting behaviour + extra behaviours, each with parameters and delay). |
| Physics | `presets/physics/` | One or more physics sets (`physicstasks.ymt` sets such as `CTaskNMShot / Shot_Base`). |

Each preset is a single `.elpreset` file (XML). See the two examples in `presets/`.

## Submitting a preset

1. In Euphoria Lab, export your stack or physics set (it saves an `.elpreset` file).
2. Post it in the Discord `#presets` channel, **or** open a pull request adding it to
   `presets/stack/` or `presets/physics/`.
3. Once it's merged, the index is rebuilt automatically and it appears in the mod.

Rules: give it a clear `<Name>` and your `<Author>` name, keep files under 200 KB,
and only share your own work.

## How it works

- `tools/build_index.py` validates every preset and writes `index.xml`
  (name, author, description, tags, type, file, date).
- The GitHub Action in `.github/workflows/build-index.yml` runs it on every push
  and commits the new `index.xml`. Invalid presets fail the check and are not published.
- The mod downloads `https://raw.githubusercontent.com/<owner>/<repo>/main/index.xml`
  and then the individual preset files.

Presets are plain data (behaviour names and numbers). The mod only reads known
fields, so a preset can't run code.

## Preset format (format 1)

```xml
<EuphoriaLabPreset format="1">
  <Name>…</Name>            <!-- required, max 60 chars -->
  <Author>…</Author>        <!-- required, max 40 chars -->
  <Description>…</Description>
  <ModVersion>1.3.0</ModVersion>
  <Tags>comma, separated</Tags>

  <!-- exactly one of: -->
  <Stack>
    <Entry behavior="StaggerFall" delay="0">
      <Param name="ArmStiffness" type="Float" value="6" />   <!-- Bool | Int | Float | Vector ("x,y,z") | String -->
    </Entry>
  </Stack>

  <PhysicsSets>
    <Set task="CTaskNMShot" label="Shot_Base" enabled="true" priority="0">
      <Messages> <!-- same <Item type="CNmMessage"> format as physicstasks.ymt XML --> </Messages>
    </Set>
  </PhysicsSets>
</EuphoriaLabPreset>
```
