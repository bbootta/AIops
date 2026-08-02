using UnrealBuildTool;

public class HopeLastStreetTarget : TargetRules
{
	public HopeLastStreetTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		// Latest rather than a pinned version, so the project opens against
		// whichever engine the user has installed.
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("HopeLastStreet");
	}
}
