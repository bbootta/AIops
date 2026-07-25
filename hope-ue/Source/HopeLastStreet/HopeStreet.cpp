#include "HopeStreet.h"

#include "HopeBlocks.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"

namespace
{
	// The film still is a dust-loaded late afternoon: a low warm sun raking
	// down the street, and enough airborne dust that the far end of the block
	// dissolves entirely. Colours are lifted from the WebGL build's grade.
	const FLinearColor SunColour(1.0f, 0.86f, 0.66f);
	const FLinearColor DustColour(0.52f, 0.47f, 0.40f);

	constexpr float M = 100.0f;   // metres -> Unreal centimetres
}

AHopeStreet::AHopeStreet()
{
	PrimaryActorTick.bCanEverTick = false;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);
}

UMaterialInterface* AHopeStreet::Mat(const FString& Key) const
{
	const TObjectPtr<UMaterialInterface>* Found = Materials.Find(Key);
	return Found ? Found->Get() : nullptr;
}

void AHopeStreet::BeginPlay()
{
	Super::BeginPlay();

	// Tint and roughness stand in until real scanned materials are assigned;
	// see README.md for the swap. Keys match /Game/Materials/M_Hope_<Key>.
	Materials.Add(TEXT("Asphalt"),  HopeBlocks::MaterialFor(this, TEXT("Asphalt"),  FLinearColor(0.055f, 0.053f, 0.050f), 0.72f));
	Materials.Add(TEXT("Sidewalk"), HopeBlocks::MaterialFor(this, TEXT("Sidewalk"), FLinearColor(0.150f, 0.142f, 0.128f), 0.88f));
	Materials.Add(TEXT("Kerb"),     HopeBlocks::MaterialFor(this, TEXT("Kerb"),     FLinearColor(0.180f, 0.172f, 0.158f), 0.85f));
	Materials.Add(TEXT("Dirt"),     HopeBlocks::MaterialFor(this, TEXT("Dirt"),     FLinearColor(0.110f, 0.095f, 0.072f), 0.95f));
	Materials.Add(TEXT("Stucco"),   HopeBlocks::MaterialFor(this, TEXT("Stucco"),   FLinearColor(0.230f, 0.212f, 0.185f), 0.90f));
	Materials.Add(TEXT("Brick"),    HopeBlocks::MaterialFor(this, TEXT("Brick"),    FLinearColor(0.140f, 0.088f, 0.070f), 0.92f));
	Materials.Add(TEXT("Shutter"),  HopeBlocks::MaterialFor(this, TEXT("Shutter"),  FLinearColor(0.085f, 0.090f, 0.092f), 0.55f, 0.85f));
	Materials.Add(TEXT("Sign"),     HopeBlocks::MaterialFor(this, TEXT("Sign"),     FLinearColor(0.320f, 0.140f, 0.095f), 0.65f));
	Materials.Add(TEXT("Awning"),   HopeBlocks::MaterialFor(this, TEXT("Awning"),   FLinearColor(0.190f, 0.145f, 0.110f), 0.88f));
	Materials.Add(TEXT("Glass"),    HopeBlocks::MaterialFor(this, TEXT("Glass"),    FLinearColor(0.020f, 0.024f, 0.028f), 0.12f));
	Materials.Add(TEXT("Metal"),    HopeBlocks::MaterialFor(this, TEXT("Metal"),    FLinearColor(0.095f, 0.100f, 0.105f), 0.45f, 0.90f));

	BuildAtmosphere();
	BuildGround();
	BuildFacades();
	BuildProps();
}

// ---------------------------------------------------------------------------
// Lighting
// ---------------------------------------------------------------------------
void AHopeStreet::BuildAtmosphere()
{
	UWorld* W = GetWorld();
	if (!W)
	{
		return;
	}

	// Sun. Pitched down 29 degrees and yawed across the street, matching the
	// raking light in the still. Movable so Lumen treats it as dynamic.
	ADirectionalLight* Sun = W->SpawnActor<ADirectionalLight>(
		ADirectionalLight::StaticClass(), FVector::ZeroVector, FRotator(-29.0f, 62.0f, 0.0f));
	if (Sun)
	{
		Sun->SetMobility(EComponentMobility::Movable);
		if (UDirectionalLightComponent* C = Cast<UDirectionalLightComponent>(Sun->GetLightComponent()))
		{
			C->SetIntensity(6.0f);
			C->SetLightColor(SunColour);
			C->LightSourceAngle = 1.2f;              // soft-edged shadows from a hazy disc
			C->bCastVolumetricShadow = true;
			C->DynamicShadowDistanceMovableLight = 20000.0f;
			C->CascadeDistributionExponent = 2.5f;
			C->MarkRenderStateDirty();
		}
	}

	// Sky atmosphere drives the dust scattering the fog then thickens.
	W->SpawnActor<AActor>(ASkyAtmosphere::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);

	// Sky light, captured from the atmosphere rather than a cubemap asset.
	ASkyLight* Sky = W->SpawnActor<ASkyLight>(
		ASkyLight::StaticClass(), FVector(0.0f, 0.0f, 500.0f), FRotator::ZeroRotator);
	if (Sky)
	{
		Sky->SetMobility(EComponentMobility::Movable);
		if (USkyLightComponent* C = Sky->GetLightComponent())
		{
			C->SourceType = SLS_CapturedScene;
			C->bRealTimeCapture = true;
			C->SetIntensity(1.0f);
			C->SetLightColor(DustColour);
			C->bCastVolumetricShadow = true;
			C->MarkRenderStateDirty();
		}
	}

	// Volumetric fog. This is the single biggest visual gain over the WebGL
	// build, which could only fake depth with billboard haze cards — and those
	// cards were what broke its ambient-occlusion pass.
	AExponentialHeightFog* Fog = W->SpawnActor<AExponentialHeightFog>(
		AExponentialHeightFog::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
	if (Fog)
	{
		if (UExponentialHeightFogComponent* C = Fog->GetComponent())
		{
			C->SetFogDensity(0.09f);
			C->SetFogHeightFalloff(0.16f);
			C->SetFogInscatteringColor(DustColour);
			C->SetStartDistance(200.0f);
			C->SetVolumetricFog(true);
			C->SetVolumetricFogExtinctionScale(1.4f);
			C->SetVolumetricFogScatteringDistribution(0.55f);
			C->SetVolumetricFogAlbedo(FColor(210, 198, 178));
			C->MarkRenderStateDirty();
		}
	}

	// Unbound post-process volume: exposure, grade and Lumen quality.
	APostProcessVolume* PP = W->SpawnActor<APostProcessVolume>(
		APostProcessVolume::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
	if (PP)
	{
		PP->bUnbound = true;
		PP->Priority = 1.0f;
		FPostProcessSettings& S = PP->Settings;

		S.bOverride_DynamicGlobalIlluminationMethod = true;
		S.DynamicGlobalIlluminationMethod = EDynamicGlobalIlluminationMethod::Lumen;
		S.bOverride_ReflectionMethod = true;
		S.ReflectionMethod = EReflectionMethod::Lumen;

		S.bOverride_LumenSceneLightingQuality = true;   S.LumenSceneLightingQuality = 2.0f;
		S.bOverride_LumenSceneDetail = true;            S.LumenSceneDetail = 2.0f;
		S.bOverride_LumenFinalGatherQuality = true;     S.LumenFinalGatherQuality = 2.0f;
		S.bOverride_LumenMaxTraceDistance = true;       S.LumenMaxTraceDistance = 30000.0f;
		S.bOverride_LumenReflectionQuality = true;      S.LumenReflectionQuality = 2.0f;

		// Manual exposure. Auto-exposure hunts badly on a scene this
		// low-contrast, which is exactly what went wrong in the WebGL build.
		S.bOverride_AutoExposureMethod = true;
		S.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
		S.bOverride_AutoExposureBias = true;
		S.AutoExposureBias = 10.6f;

		S.bOverride_BloomIntensity = true;              S.BloomIntensity = 0.42f;
		S.bOverride_BloomThreshold = true;              S.BloomThreshold = 1.1f;

		S.bOverride_FilmGrainIntensity = true;          S.FilmGrainIntensity = 0.22f;
		S.bOverride_VignetteIntensity = true;           S.VignetteIntensity = 0.42f;
		S.bOverride_SceneFringeIntensity = true;        S.SceneFringeIntensity = 1.6f;
		S.bOverride_MotionBlurAmount = true;            S.MotionBlurAmount = 0.32f;
		S.bOverride_DepthOfFieldFocalDistance = true;   S.DepthOfFieldFocalDistance = 900.0f;
		S.bOverride_DepthOfFieldFstop = true;           S.DepthOfFieldFstop = 5.0f;

		// Bleached, dust-warm grade: pull saturation down, push the shadows
		// cool and the midtones warm.
		S.bOverride_ColorSaturation = true;   S.ColorSaturation = FVector4(0.86f, 0.87f, 0.90f, 1.0f);
		S.bOverride_ColorContrast = true;     S.ColorContrast   = FVector4(1.08f, 1.06f, 1.02f, 1.0f);
		S.bOverride_ColorGain = true;         S.ColorGain       = FVector4(1.05f, 1.00f, 0.92f, 1.0f);
		S.bOverride_ColorGamma = true;        S.ColorGamma      = FVector4(1.00f, 0.99f, 1.02f, 1.0f);
	}
}

// ---------------------------------------------------------------------------
// Ground
// ---------------------------------------------------------------------------
void AHopeStreet::BuildGround()
{
	const float Len = StreetLength * M;
	const float HalfW = StreetWidth * 0.5f * M;
	const FVector Mid(Len * 0.5f - 12.0f * M, 0.0f, 0.0f);

	// Dirt shelf under everything, so the gaps between lots are never void.
	HopeBlocks::AddBox(this, Root, FVector(90000.0f, 90000.0f, 20.0f),
		FVector(Mid.X, 0.0f, -12.0f), FRotator::ZeroRotator, Mat(TEXT("Dirt")));

	// Road slab.
	HopeBlocks::AddBox(this, Root, FVector(Len + 6000.0f, HalfW * 2.0f, 10.0f),
		FVector(Mid.X, 0.0f, -3.0f), FRotator::ZeroRotator, Mat(TEXT("Asphalt")));

	// Centre line, as its own strip. In the WebGL build this was baked into the
	// road texture, which tiles across the width — so it painted a line in
	// every lane. Keeping it separate is the fix.
	HopeBlocks::AddBox(this, Root, FVector(Len + 6000.0f, 22.0f, 2.0f),
		FVector(Mid.X, 0.0f, 3.0f), FRotator::ZeroRotator, Mat(TEXT("Sidewalk")));

	for (int32 Side = -1; Side <= 1; Side += 2)
	{
		const float S = static_cast<float>(Side);
		// Kerb.
		HopeBlocks::AddBox(this, Root, FVector(Len + 6000.0f, 40.0f, 20.0f),
			FVector(Mid.X, S * (HalfW + 20.0f), 10.0f), FRotator::ZeroRotator, Mat(TEXT("Kerb")));
		// Pavement.
		HopeBlocks::AddBox(this, Root, FVector(Len + 6000.0f, 640.0f, 20.0f),
			FVector(Mid.X, S * (HalfW + 360.0f), 10.0f), FRotator::ZeroRotator, Mat(TEXT("Sidewalk")));
	}
}

// ---------------------------------------------------------------------------
// Shop fronts
// ---------------------------------------------------------------------------
void AHopeStreet::BuildFacades()
{
	// Same seed as the WebGL build, so the block reads the same way.
	FRandomStream Rng(20240721);

	for (int32 Side = -1; Side <= 1; Side += 2)
	{
		float X = -800.0f;
		int32 Lot = 0;
		while (X < StreetLength * M)
		{
			const float Width = (9.0f + Rng.FRand() * 6.0f) * M;
			// Every sixth lot is a collapsed gap, which is what lets the eye
			// read depth down the block.
			if (Lot % 6 != 5)
			{
				BuildShop(static_cast<float>(Side), X + Width * 0.5f, Width, Rng);
			}
			X += Width + 0.4f * M;
			++Lot;
		}
	}
}

void AHopeStreet::BuildShop(float Side, float CentreX, float Width, FRandomStream& Rng)
{
	const float Depth = (7.0f + Rng.FRand() * 3.0f) * M;
	const float Height = (7.0f + Rng.FRand() * 8.0f) * M;
	const float FrontY = Side * (StreetWidth * 0.5f * M + 680.0f);
	const float CentreY = FrontY + Side * Depth * 0.5f;

	UMaterialInterface* Shell = Mat(Rng.FRand() < 0.45f ? TEXT("Brick") : TEXT("Stucco"));

	// Shell. Solid, because the interiors are never entered — Lumen still
	// bounces sun off the facade into the street, which is the point.
	HopeBlocks::AddBox(this, Root, FVector(Width, Depth, Height),
		FVector(CentreX, CentreY, Height * 0.5f + 20.0f), FRotator::ZeroRotator, Shell);

	// Ground floor: a dark recessed shopfront with a shutter half drawn.
	const float ShutterDrop = (0.3f + Rng.FRand() * 0.55f);
	HopeBlocks::AddBox(this, Root, FVector(Width * 0.82f, 12.0f, 320.0f * ShutterDrop),
		FVector(CentreX, FrontY - Side * 6.0f, 20.0f + 320.0f * (1.0f - ShutterDrop * 0.5f)),
		FRotator::ZeroRotator, Mat(TEXT("Shutter")));
	HopeBlocks::AddBox(this, Root, FVector(Width * 0.82f, 8.0f, 320.0f),
		FVector(CentreX, FrontY - Side * 2.0f, 180.0f), FRotator::ZeroRotator, Mat(TEXT("Glass")));

	// Upper windows.
	const int32 Floors = FMath::Max(1, FMath::FloorToInt((Height - 340.0f) / 300.0f));
	const int32 Bays = FMath::Max(1, FMath::FloorToInt(Width / 260.0f));
	for (int32 F = 0; F < Floors; ++F)
	{
		for (int32 B = 0; B < Bays; ++B)
		{
			if (Rng.FRand() < 0.12f)
			{
				continue;   // boarded up
			}
			const float WX = CentreX - Width * 0.5f + Width * (B + 0.5f) / Bays;
			const float WZ = 420.0f + F * 300.0f;
			HopeBlocks::AddBox(this, Root, FVector(130.0f, 10.0f, 165.0f),
				FVector(WX, FrontY - Side * 4.0f, WZ), FRotator::ZeroRotator, Mat(TEXT("Glass")));
			// Frame.
			HopeBlocks::AddBox(this, Root, FVector(150.0f, 14.0f, 12.0f),
				FVector(WX, FrontY - Side * 8.0f, WZ + 88.0f), FRotator::ZeroRotator, Mat(TEXT("Metal")));
		}
	}

	// Awning over the shopfront.
	if (Rng.FRand() < 0.55f)
	{
		HopeBlocks::AddBox(this, Root, FVector(Width * 0.86f, 150.0f, 10.0f),
			FVector(CentreX, FrontY - Side * 78.0f, 330.0f), FRotator(0.0f, 0.0f, Side * 8.0f),
			Mat(TEXT("Awning")));
	}

	// Hangul shop sign. The lettering itself is a texture on the generated
	// material; without build_content.py this is a flat painted board.
	HopeBlocks::AddBox(this, Root, FVector(Width * 0.9f, 16.0f, 110.0f),
		FVector(CentreX, FrontY - Side * 14.0f, 400.0f), FRotator::ZeroRotator, Mat(TEXT("Sign")));
}

// ---------------------------------------------------------------------------
// Street furniture
// ---------------------------------------------------------------------------
void AHopeStreet::BuildProps()
{
	FRandomStream Rng(88117);

	// Power poles with slack wires, both sides of the street.
	for (float X = 0.0f; X < StreetLength * M; X += 1800.0f)
	{
		for (int32 Side = -1; Side <= 1; Side += 2)
		{
			const float S = static_cast<float>(Side);
			const float Y = S * (StreetWidth * 0.5f * M + 120.0f);
			HopeBlocks::AddBox(this, Root, FVector(26.0f, 26.0f, 820.0f),
				FVector(X, Y, 430.0f), FRotator(0.0f, 0.0f, Rng.FRandRange(-2.0f, 2.0f)),
				Mat(TEXT("Metal")));
			HopeBlocks::AddBox(this, Root, FVector(20.0f, 240.0f, 14.0f),
				FVector(X, Y - S * 90.0f, 790.0f), FRotator::ZeroRotator, Mat(TEXT("Metal")));
			// Wire to the next pole, sagging.
			HopeBlocks::AddBox(this, Root, FVector(1800.0f, 5.0f, 5.0f),
				FVector(X + 900.0f, Y - S * 90.0f, 750.0f),
				FRotator(1.2f, 0.0f, 0.0f), Mat(TEXT("Metal")));
		}
	}

	// Abandoned sedans, angled across the lanes.
	for (int32 i = 0; i < 9; ++i)
	{
		const float X = 900.0f + i * 2100.0f + Rng.FRandRange(-400.0f, 400.0f);
		const float Y = Rng.FRandRange(-420.0f, 420.0f);
		const float Yaw = Rng.FRandRange(-38.0f, 38.0f);
		const FRotator Rot(0.0f, Yaw, 0.0f);

		HopeBlocks::AddBox(this, Root, FVector(430.0f, 178.0f, 78.0f),
			FVector(X, Y, 74.0f), Rot, Mat(TEXT("Metal")));
		HopeBlocks::AddBox(this, Root, FVector(215.0f, 165.0f, 66.0f),
			FVector(X - 18.0f, Y, 142.0f), Rot, Mat(TEXT("Glass")));
	}

	// Rubble. Small, plentiful, and never in the middle of the firing lane.
	for (int32 i = 0; i < 220; ++i)
	{
		const float X = Rng.FRandRange(-500.0f, StreetLength * M);
		const float Y = Rng.FRandRange(-900.0f, 900.0f);
		const float Size = Rng.FRandRange(12.0f, 58.0f);
		HopeBlocks::AddBox(this, Root, FVector(Size, Size * Rng.FRandRange(0.6f, 1.4f), Size * 0.6f),
			FVector(X, Y, Size * 0.3f + 20.0f),
			FRotator(Rng.FRandRange(-14.0f, 14.0f), Rng.FRandRange(0.0f, 360.0f), Rng.FRandRange(-14.0f, 14.0f)),
			Mat(Rng.FRand() < 0.5f ? TEXT("Sidewalk") : TEXT("Brick")));
	}
}
