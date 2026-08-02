#pragma once

#include "CoreMinimal.h"

class AActor;
class USceneComponent;
class UStaticMeshComponent;
class UMaterialInterface;

/**
 * Small helpers for assembling actors out of engine primitive meshes at
 * runtime. The whole street, the officer and the shadows are built this way so
 * the project runs straight from a clone with no .uasset content of its own.
 *
 * These are placeholder proportions, not photoreal geometry. See README.md
 * ("Where the photorealism actually comes from") for the asset swap.
 */
namespace HopeBlocks
{
	/** Engine unit cube, 100cm on a side, centred on its origin. */
	UStaticMesh* CubeMesh();

	/**
	 * Attaches a box of the given world size (cm) to Parent.
	 * Size is the finished size, not a scale factor.
	 */
	UStaticMeshComponent* AddBox(
		AActor* Owner,
		USceneComponent* Parent,
		const FVector& Size,
		const FVector& Location,
		const FRotator& Rotation,
		UMaterialInterface* Material);

	/**
	 * Resolves a project material by key, e.g. "Asphalt" -> /Game/Materials/M_Hope_Asphalt.
	 * Falls back to a tinted instance of the engine's basic shape material when
	 * Tools/build_content.py has not been run, so nothing renders untextured
	 * white. Tint and Roughness are applied to whichever base is found.
	 */
	UMaterialInterface* MaterialFor(
		UObject* Outer,
		const FString& Key,
		const FLinearColor& Tint,
		float Roughness = 0.8f,
		float Metallic = 0.0f);
}
