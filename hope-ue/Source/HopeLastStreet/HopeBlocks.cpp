#include "HopeBlocks.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

namespace HopeBlocks
{
	UStaticMesh* CubeMesh()
	{
		static UStaticMesh* Cached = nullptr;
		if (!Cached)
		{
			Cached = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
		}
		return Cached;
	}

	UStaticMeshComponent* AddBox(
		AActor* Owner,
		USceneComponent* Parent,
		const FVector& Size,
		const FVector& Location,
		const FRotator& Rotation,
		UMaterialInterface* Material)
	{
		if (!Owner || !Parent)
		{
			return nullptr;
		}

		UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(Owner);
		Mesh->SetStaticMesh(CubeMesh());
		Mesh->SetupAttachment(Parent);
		Mesh->RegisterComponent();
		Mesh->SetRelativeLocation(Location);
		Mesh->SetRelativeRotation(Rotation);
		// The engine cube is 100cm on a side, so the scale is the size in metres.
		Mesh->SetRelativeScale3D(Size / 100.0f);

		if (Material)
		{
			Mesh->SetMaterial(0, Material);
		}

		// Movable is forced, not chosen: a component created after the level
		// has loaded cannot be Static. The street therefore costs Lumen more
		// than an authored level would — building it in the editor instead is
		// the fix if that ever shows up in a profile.
		Mesh->SetMobility(EComponentMobility::Movable);
		Mesh->SetCastShadow(true);

		return Mesh;
	}

	UMaterialInterface* MaterialFor(
		UObject* Outer,
		const FString& Key,
		const FLinearColor& Tint,
		float Roughness,
		float Metallic)
	{
		// Preferred: the material instance built by Tools/build_content.py and
		// possibly re-pointed at a scanned surface by Tools/import_megascans.py.
		UMaterialInterface* Base = LoadObject<UMaterialInterface>(
			nullptr, *FString::Printf(TEXT("/Game/Materials/MI_Hope_%s.MI_Hope_%s"), *Key, *Key));

		// Last resort: neither script has been run. The engine's basic shape
		// material at least takes a colour, so the street reads as a street
		// rather than as untextured white.
		const bool bGenerated = Base != nullptr;
		if (!Base)
		{
			Base = LoadObject<UMaterialInterface>(
				nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
		}

		if (!Base)
		{
			return nullptr;
		}

		UMaterialInstanceDynamic* Instance = UMaterialInstanceDynamic::Create(Base, Outer);
		if (!Instance)
		{
			return Base;
		}

		if (bGenerated)
		{
			// The instance already carries its tint, roughness and tiling, and
			// import_megascans.py neutralises the tint to white when it assigns
			// a scanned albedo. Overwriting those here would multiply a scan
			// back down to the placeholder colour and undo the import — so the
			// generated instance is left exactly as authored.
			return Instance;
		}

		Instance->SetVectorParameterValue(TEXT("Color"), Tint);
		Instance->SetScalarParameterValue(TEXT("Roughness"), Roughness);
		Instance->SetScalarParameterValue(TEXT("Metallic"), Metallic);

		return Instance;
	}
}
