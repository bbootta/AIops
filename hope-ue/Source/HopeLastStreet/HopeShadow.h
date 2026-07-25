#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HopeShadow.generated.h"

class UCapsuleComponent;
class USceneComponent;
class UMaterialInstanceDynamic;

/**
 * The shadow creature. Tall, thin, and lit almost entirely by Lumen bounce —
 * it reads as a silhouette against the dust rather than a shaded model, which
 * is what the film still does with it.
 *
 * Deliberately not a Character: it walks a flat street toward the player, so a
 * movement component, a controller and a navmesh would all be dead weight.
 */
UCLASS()
class HOPELASTSTREET_API AHopeShadow : public AActor
{
	GENERATED_BODY()

public:
	AHopeShadow();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Called by the wave director immediately after spawn. */
	void Configure(int32 Wave, bool bInBrute);

	/** Damage is in hits, not points: 1 for a body shot, 3 for a head shot. */
	void TakeShadowDamage(float Amount, bool bHeadshot);

	/** Height above the actor origin where the head starts, for headshots. */
	float GetHeadHeightOffset() const;

	bool IsAlive() const { return State == EShadowState::Walk; }
	bool IsBrute() const { return bBrute; }

private:
	enum class EShadowState : uint8 { Walk, Dying };

	EShadowState State = EShadowState::Walk;

	float Health = 3.0f;
	float Speed = 155.0f;
	float Height = 235.0f;
	bool bBrute = false;

	float DyingTimer = 0.0f;
	float HitFlash = 0.0f;
	float AttackCooldown = 0.0f;
	float GaitPhase = 0.0f;

	UPROPERTY() TObjectPtr<UCapsuleComponent> Capsule;
	UPROPERTY() TObjectPtr<USceneComponent> Body;
	UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> Skins;

	UPROPERTY() TObjectPtr<USceneComponent> LeftLeg;
	UPROPERTY() TObjectPtr<USceneComponent> RightLeg;
	UPROPERTY() TObjectPtr<USceneComponent> LeftArm;
	UPROPERTY() TObjectPtr<USceneComponent> RightArm;

	void BuildSilhouette();
	USceneComponent* AddLimb(const FVector& Offset, const FVector& Size);
};
