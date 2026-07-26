#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "HopeCharacter.generated.h"

class USpringArmComponent;
class UCineCameraComponent;
class UPointLightComponent;
class USceneComponent;
class UStaticMeshComponent;

/**
 * The officer. Third person, over the right shoulder, to match the framing of
 * the film still the game is built from.
 *
 * The body is assembled from primitives — a placeholder, and the one part of
 * this project that photorealism does NOT come from. A MetaHuman replaces it;
 * see README.md. Everything below the mesh (aim, recoil, the two-handed carry)
 * is written so the swap is a mesh change, not a rewrite.
 */
UCLASS()
class HOPELASTSTREET_API AHopeCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AHopeCharacter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

	/** Ported from the WebGL build so the two versions play identically. */
	static constexpr int32 MagazineSize = 30;
	static constexpr float ReloadSeconds = 1.7f;
	static constexpr float FireInterval = 0.092f;
	static constexpr float MaxHealth = 100.0f;
	static constexpr float TraceRange = 22000.0f;

	/**
	 * Focal lengths in millimetres on a Super 35 sensor, so the framing change
	 * on aiming is a lens change rather than an arbitrary field-of-view lerp.
	 * 18mm gives roughly 69 degrees horizontal, 40mm roughly 35.
	 */
	static constexpr float LensWide = 18.0f;
	static constexpr float LensAimed = 40.0f;

	int32 Ammo = MagazineSize;
	int32 Reserve = 150;
	float Health = MaxHealth;
	bool bReloading = false;
	bool bAiming = false;

	/** Damage entry point used by the shadows. Returns true if this was fatal. */
	bool ApplyShadowHit(float Amount);

	void GiveAmmo(int32 Rounds);
	void Heal(float Amount);

	/** Set false on death so input stops driving the pawn. */
	bool bAlive = true;

private:
	void MoveForward(float Value);
	void MoveRight(float Value);
	void Turn(float Value);
	void LookUp(float Value);
	void StartFire();
	void StopFire();
	void StartAim();
	void StopAim();
	void StartSprint();
	void StopSprint();
	void Reload();
	void Restart();

	void FireOnce();

	/** Pulls focus onto whatever the officer is looking at. */
	void UpdateFocus(float DeltaSeconds);

	/**
	 * Uses a MetaHuman (or any skeletal mesh) dropped at
	 * /Game/Characters/Officer instead of the primitive body, if one is there.
	 * Returns true when it took over. See README.
	 */
	bool ApplyScannedCharacter();

	void BuildPlaceholderBody();

	UPROPERTY() TObjectPtr<USpringArmComponent> Boom;
	UPROPERTY() TObjectPtr<UCineCameraComponent> Camera;
	UPROPERTY() TObjectPtr<USceneComponent> BodyRoot;
	UPROPERTY() TObjectPtr<USceneComponent> RifleRoot;
	UPROPERTY() TObjectPtr<USceneComponent> MuzzleSocket;
	UPROPERTY() TObjectPtr<UPointLightComponent> MuzzleLight;

	bool bFiring = false;
	bool bSprinting = false;
	float FireCooldown = 0.0f;
	float ReloadTimer = 0.0f;
	float Recoil = 0.0f;       // decays to zero, drives the rifle kick
	float MuzzleTimer = 0.0f;

	/**
	 * True once the rifle is parented to a skeleton's hand socket. The hand
	 * then owns its transform, so Tick must stop writing one — otherwise the
	 * two fight and the weapon jitters between them every frame.
	 */
	bool bRifleOnSocket = false;
};
