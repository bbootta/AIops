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
		UMaterialInterface* Base = LoadObject<UMaterialInterface>(
			nullptr, *FString::Printf(TEXT("/Game/Materials/M_Hope_%s.M_Hope_%s"), *Key, *Key));

		if (!Base)
		{
			// build_content.py has not been run. Fall back to the engine's
			// basic shape material so the street is at least correctly
			// coloured rather than default white.
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

		// Parameter names that miss are ignored, so the same call works against
		// the generated materials and against the engine fallback.
		Instance->SetVectorParameterValue(TEXT("Color"), Tint);
		Instance->SetVectorParameterValue(TEXT("BaseColorTint"), Tint);
		Instance->SetScalarParameterValue(TEXT("Roughness"), Roughness);
		Instance->SetScalarParameterValue(TEXT("Metallic"), Metallic);

		return Instance;
	}
}
