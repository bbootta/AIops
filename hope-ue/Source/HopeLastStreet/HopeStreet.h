#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HopeStreet.generated.h"

class UMaterialInterface;

/**
 * Builds the ruined street and its lighting.
 *
 * Layout, dimensions and the seeded shop-front variation are ported from the
 * WebGL build (hope-shooter/src/world.js) so the two versions frame the same
 * scene. What changes here is what the renderer does with it: Lumen carries
 * the bounce light into the shop interiors, virtual shadow maps replace the
 * cascades, and volumetric fog replaces the billboard haze cards.
 */
UCLASS()
class HOPELASTSTREET_API AHopeStreet : public AActor
{
	GENERATED_BODY()

public:
	AHopeStreet();

	/** Street runs down -X from the spawn point. Metres, as in the WebGL build. */
	static constexpr float StreetLength = 210.0f;
	static constexpr float StreetWidth = 14.0f;

	virtual void BeginPlay() override;

private:
	void BuildAtmosphere();
	void BuildGround();
	void BuildFacades();
	void BuildProps();

	/** One shop front: shell, recessed windows, shutter, awning, hangul sign. */
	void BuildShop(float Side, float CentreY, float Width, FRandomStream& Rng);

	UPROPERTY() TObjectPtr<USceneComponent> Root;
	UPROPERTY() TMap<FString, TObjectPtr<UMaterialInterface>> Materials;

	UMaterialInterface* Mat(const FString& Key) const;
};
