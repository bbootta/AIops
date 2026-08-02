using UnrealBuildTool;

public class HopeLastStreet : ModuleRules
{
	public HopeLastStreet(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			// Physical camera: focal length, aperture and sensor size, so
			// exposure and depth of field are driven by real quantities
			// rather than by numbers picked until the picture looked right.
			"CinematicCamera",
		});
	}
}
