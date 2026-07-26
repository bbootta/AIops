#include "HopeCharacter.h"

#include "HopeBlocks.h"
#include "HopeGameMode.h"
#include "HopeShadow.h"

#include "Animation/AnimInstance.h"
#include "CineCameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"

namespace
{
	// Metres per second in the WebGL build, centimetres per second here.
	constexpr float SpeedWalk = 410.0f;
	constexpr float SpeedSprint = 700.0f;
	constexpr float SpeedAiming = 240.0f;

	// Cone half-angles in degrees. The WebGL build expressed these as
	// normalised-device offsets; converted here at the game's field of view.
	constexpr float SpreadAimed = 0.17f;
	constexpr float SpreadHip = 0.52f;
	constexpr float SpreadMoving = 0.70f;
}

AHopeCharacter::AHopeCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(38.0f, 92.0f);

	// The officer faces where the player aims; the camera owns the yaw.
	bUseControllerRotationYaw = true;
	bUseControllerRotationPitch = false;
	bUseControllerRotationRoll = false;

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->bOrientRotationToMovement = false;
		Move->MaxWalkSpeed = SpeedWalk;
		Move->MaxAcceleration = 1800.0f;
		Move->BrakingDecelerationWalking = 2200.0f;
		Move->GravityScale = 1.35f;
		Move->AirControl = 0.15f;
	}

	// Over the right shoulder. bDoCollisionTest is what pulls the camera in
	// when the officer backs into a shopfront.
	Boom = CreateDefaultSubobject<USpringArmComponent>(TEXT("Boom"));
	Boom->SetupAttachment(GetCapsuleComponent());
	Boom->TargetArmLength = 260.0f;
	Boom->SocketOffset = FVector(0.0f, 62.0f, 58.0f);
	Boom->bUsePawnControlRotation = true;
	Boom->bDoCollisionTest = true;
	Boom->ProbeSize = 14.0f;
	Boom->bEnableCameraLag = true;
	Boom->CameraLagSpeed = 18.0f;
	Boom->bEnableCameraRotationLag = true;
	Boom->CameraRotationLagSpeed = 22.0f;

	// A real camera: Super 35 sensor, an 18mm lens wide open at f/8. The
	// aperture is not a look preference — it is half of the exposure the
	// street's 32,000 lux sun is metered against, in HopeStreet.
	Camera = CreateDefaultSubobject<UCineCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(Boom, USpringArmComponent::SocketName);
	Camera->bUsePawnControlRotation = false;
	Camera->Filmback.SensorWidth = 24.89f;
	Camera->Filmback.SensorHeight = 18.66f;
	Camera->CurrentFocalLength = LensWide;
	Camera->CurrentAperture = 8.0f;
	// Focus is pulled onto whatever is downrange, so the far end of the block
	// goes soft the way it does in the still.
	Camera->FocusSettings.FocusMethod = ECameraFocusMethod::Manual;
	Camera->FocusSettings.ManualFocusDistance = 900.0f;
	Camera->FocusSettings.bSmoothFocusChanges = true;
	Camera->FocusSettings.FocusSmoothingInterpSpeed = 6.0f;

	BodyRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BodyRoot"));
	BodyRoot->SetupAttachment(GetCapsuleComponent());

	RifleRoot = CreateDefaultSubobject<USceneComponent>(TEXT("RifleRoot"));
	RifleRoot->SetupAttachment(GetCapsuleComponent());

	MuzzleSocket = CreateDefaultSubobject<USceneComponent>(TEXT("MuzzleSocket"));
	MuzzleSocket->SetupAttachment(RifleRoot);
	MuzzleSocket->SetRelativeLocation(FVector(86.0f, 0.0f, 0.0f));

	MuzzleLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("MuzzleLight"));
	MuzzleLight->SetupAttachment(MuzzleSocket);
	MuzzleLight->SetIntensity(0.0f);
	MuzzleLight->SetAttenuationRadius(1400.0f);
	MuzzleLight->SetLightColor(FLinearColor(1.0f, 0.78f, 0.42f));
	MuzzleLight->SetCastShadows(true);
	MuzzleLight->SetMobility(EComponentMobility::Movable);
}

void AHopeCharacter::BeginPlay()
{
	Super::BeginPlay();

	if (!ApplyScannedCharacter())
	{
		BuildPlaceholderBody();
	}

	UMaterialInterface* Gun = HopeBlocks::MaterialFor(this, TEXT("Metal"), FLinearColor(0.035f, 0.036f, 0.038f), 0.38f, 0.85f);
	UMaterialInterface* Sling = HopeBlocks::MaterialFor(this, TEXT("Fabric"), FLinearColor(0.055f, 0.058f, 0.062f), 0.88f);

	// Rifle, carried right-handed: stock into the right shoulder, muzzle on
	// the aim line. Getting this wrong is what put the stock behind his back
	// in the WebGL build.
	HopeBlocks::AddBox(this, RifleRoot, FVector(96.0f, 7.0f, 8.0f), FVector(20.0f, 0.0f, 0.0f), FRotator::ZeroRotator, Gun);
	HopeBlocks::AddBox(this, RifleRoot, FVector(30.0f, 9.0f, 20.0f), FVector(-16.0f, 0.0f, -4.0f), FRotator::ZeroRotator, Gun);
	HopeBlocks::AddBox(this, RifleRoot, FVector(14.0f, 8.0f, 24.0f), FVector(-2.0f, 0.0f, -18.0f), FRotator(12.0f, 0.0f, 0.0f), Gun);
	HopeBlocks::AddBox(this, RifleRoot, FVector(12.0f, 7.0f, 30.0f), FVector(18.0f, 0.0f, -18.0f), FRotator::ZeroRotator, Gun);
	HopeBlocks::AddBox(this, RifleRoot, FVector(26.0f, 6.0f, 7.0f), FVector(-38.0f, 0.0f, -2.0f), FRotator::ZeroRotator, Sling);
}

bool AHopeCharacter::ApplyScannedCharacter()
{
	// Drop a MetaHuman — or any skeletal mesh — at these paths and it takes
	// over from the primitive body with no code change. Nothing here is
	// required; both loads failing is the normal, shipped state.
	USkeletalMesh* Scanned = LoadObject<USkeletalMesh>(
		nullptr, TEXT("/Game/Characters/Officer/SK_Officer.SK_Officer"));

	if (!Scanned || !GetMesh())
	{
		return false;
	}

	GetMesh()->SetSkeletalMesh(Scanned);
	// The capsule is 92cm half-height and a skeletal mesh has its origin at
	// the feet, facing +X; UE's convention is -90 yaw to line that up.
	GetMesh()->SetRelativeLocation(FVector(0.0f, 0.0f, -92.0f));
	GetMesh()->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	GetMesh()->SetCastShadow(true);
	// Skinned geometry only reaches Lumen's hardware ray tracing through the
	// GPU skin cache, which is a project setting — r.SkinCache.CompileShaders
	// is already on in DefaultEngine.ini. Without it he would light and shadow
	// correctly in the raster pass and be invisible to bounce light.

	// An animation blueprint at the sibling path, if one was authored. Without
	// it the mesh loads in its reference pose and slides — the mesh is the
	// easy half of the swap, the animation is the real work.
	if (UClass* AnimClass = LoadClass<UAnimInstance>(
		nullptr, TEXT("/Game/Characters/Officer/ABP_Officer.ABP_Officer_C")))
	{
		GetMesh()->SetAnimInstanceClass(AnimClass);
	}

	// Carry the rifle from the right hand if the skeleton offers the socket,
	// which every UE-standard and MetaHuman skeleton does.
	if (GetMesh()->DoesSocketExist(TEXT("hand_r")))
	{
		RifleRoot->AttachToComponent(
			GetMesh(), FAttachmentTransformRules::SnapToTargetNotIncludingScale, TEXT("hand_r"));
		bRifleOnSocket = true;
	}

	return true;
}

void AHopeCharacter::BuildPlaceholderBody()
{
	UMaterialInterface* Leather = HopeBlocks::MaterialFor(this, TEXT("Leather"), FLinearColor(0.045f, 0.038f, 0.034f), 0.42f);
	UMaterialInterface* Fabric = HopeBlocks::MaterialFor(this, TEXT("Fabric"), FLinearColor(0.055f, 0.058f, 0.062f), 0.88f);
	UMaterialInterface* Skin = HopeBlocks::MaterialFor(this, TEXT("Skin"), FLinearColor(0.42f, 0.30f, 0.24f), 0.62f);

	// Officer, in the police jacket of the film still. Placeholder proportions.
	HopeBlocks::AddBox(this, BodyRoot, FVector(30.0f, 46.0f, 62.0f), FVector(0.0f, 0.0f, 18.0f), FRotator::ZeroRotator, Leather);
	HopeBlocks::AddBox(this, BodyRoot, FVector(26.0f, 34.0f, 48.0f), FVector(0.0f, 0.0f, -34.0f), FRotator::ZeroRotator, Fabric);
	HopeBlocks::AddBox(this, BodyRoot, FVector(21.0f, 22.0f, 26.0f), FVector(2.0f, 0.0f, 62.0f), FRotator::ZeroRotator, Skin);
	// Shoulder patch, the one bit of colour on him.
	HopeBlocks::AddBox(this, BodyRoot, FVector(4.0f, 12.0f, 12.0f),
		FVector(0.0f, -24.0f, 36.0f), FRotator::ZeroRotator,
		HopeBlocks::MaterialFor(this, TEXT("Patch"), FLinearColor(0.18f, 0.22f, 0.42f), 0.7f));
}

void AHopeCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	PlayerInputComponent->BindAxis(TEXT("MoveForward"), this, &AHopeCharacter::MoveForward);
	PlayerInputComponent->BindAxis(TEXT("MoveRight"), this, &AHopeCharacter::MoveRight);
	PlayerInputComponent->BindAxis(TEXT("Turn"), this, &AHopeCharacter::Turn);
	PlayerInputComponent->BindAxis(TEXT("LookUp"), this, &AHopeCharacter::LookUp);

	PlayerInputComponent->BindAction(TEXT("Fire"), IE_Pressed, this, &AHopeCharacter::StartFire);
	PlayerInputComponent->BindAction(TEXT("Fire"), IE_Released, this, &AHopeCharacter::StopFire);
	PlayerInputComponent->BindAction(TEXT("Aim"), IE_Pressed, this, &AHopeCharacter::StartAim);
	PlayerInputComponent->BindAction(TEXT("Aim"), IE_Released, this, &AHopeCharacter::StopAim);
	PlayerInputComponent->BindAction(TEXT("Sprint"), IE_Pressed, this, &AHopeCharacter::StartSprint);
	PlayerInputComponent->BindAction(TEXT("Sprint"), IE_Released, this, &AHopeCharacter::StopSprint);
	PlayerInputComponent->BindAction(TEXT("Reload"), IE_Pressed, this, &AHopeCharacter::Reload);
	PlayerInputComponent->BindAction(TEXT("Restart"), IE_Pressed, this, &AHopeCharacter::Restart);
}

void AHopeCharacter::Restart()
{
	if (AHopeGameMode* GM = GetWorld()->GetAuthGameMode<AHopeGameMode>())
	{
		GM->RequestRestart();
	}
}

void AHopeCharacter::MoveForward(float Value)
{
	if (bAlive && Value != 0.0f)
	{
		AddMovementInput(FRotationMatrix(FRotator(0.0f, GetControlRotation().Yaw, 0.0f)).GetUnitAxis(EAxis::X), Value);
	}
}

void AHopeCharacter::MoveRight(float Value)
{
	if (bAlive && Value != 0.0f)
	{
		AddMovementInput(FRotationMatrix(FRotator(0.0f, GetControlRotation().Yaw, 0.0f)).GetUnitAxis(EAxis::Y), Value);
	}
}

void AHopeCharacter::Turn(float Value)
{
	// Aim follows raw mouse movement, always. In the WebGL build this was
	// gated on pointer lock, and when Electron refused the lock the player
	// could not look around at all.
	AddControllerYawInput(Value * (bAiming ? 0.55f : 1.0f));
}

void AHopeCharacter::LookUp(float Value)
{
	AddControllerPitchInput(Value * (bAiming ? 0.55f : 1.0f));
}

void AHopeCharacter::StartFire() { bFiring = true; }
void AHopeCharacter::StopFire() { bFiring = false; }
void AHopeCharacter::StartAim() { bAiming = true; }
void AHopeCharacter::StopAim() { bAiming = false; }
void AHopeCharacter::StartSprint() { bSprinting = true; }
void AHopeCharacter::StopSprint() { bSprinting = false; }

void AHopeCharacter::Reload()
{
	if (bReloading || Ammo == MagazineSize || Reserve <= 0 || !bAlive)
	{
		return;
	}
	bReloading = true;
	ReloadTimer = ReloadSeconds;
}

void AHopeCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const bool bMoving = GetVelocity().SizeSquared2D() > 400.0f;

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = bAiming ? SpeedAiming : (bSprinting ? SpeedSprint : SpeedWalk);
	}

	// Camera tightens and the field of view narrows when aiming.
	Boom->TargetArmLength = FMath::FInterpTo(Boom->TargetArmLength, bAiming ? 155.0f : 260.0f, DeltaSeconds, 9.0f);
	Boom->SocketOffset = FMath::VInterpTo(Boom->SocketOffset,
		bAiming ? FVector(0.0f, 46.0f, 46.0f) : FVector(0.0f, 62.0f, 58.0f), DeltaSeconds, 9.0f);
	Camera->CurrentFocalLength = FMath::FInterpTo(
		Camera->CurrentFocalLength, bAiming ? LensAimed : LensWide, DeltaSeconds, 9.0f);
	UpdateFocus(DeltaSeconds);

	if (bReloading)
	{
		ReloadTimer -= DeltaSeconds;
		if (ReloadTimer <= 0.0f)
		{
			const int32 Take = FMath::Min(MagazineSize - Ammo, Reserve);
			Ammo += Take;
			Reserve -= Take;
			bReloading = false;
		}
	}

	// The rifle rides at the shoulder, swinging up onto the aim line. Recoil
	// pitches it and is fed back into the camera as kick.
	Recoil = FMath::FInterpTo(Recoil, 0.0f, DeltaSeconds, 11.0f);
	if (!bRifleOnSocket)
	{
		const FVector RestLoc(38.0f, 26.0f, 24.0f);
		const FVector AimLoc(46.0f, 12.0f, 34.0f);
		RifleRoot->SetRelativeLocation(FMath::VInterpTo(
			RifleRoot->GetRelativeLocation(), bAiming ? AimLoc : RestLoc, DeltaSeconds, 14.0f));
		RifleRoot->SetRelativeRotation(FRotator(
			-Recoil * 7.0f, bAiming ? 0.0f : 6.0f, bAiming ? 0.0f : 4.0f));
	}

	MuzzleTimer = FMath::Max(0.0f, MuzzleTimer - DeltaSeconds);
	MuzzleLight->SetIntensity(MuzzleTimer > 0.0f ? 220.0f * (MuzzleTimer / 0.045f) : 0.0f);

	FireCooldown -= DeltaSeconds;
	if (bFiring && bAlive && !bReloading && FireCooldown <= 0.0f)
	{
		if (Ammo <= 0)
		{
			bFiring = false;
			Reload();
		}
		else
		{
			FireOnce();
			FireCooldown = FireInterval;
		}
	}

	// Recoil climb while holding the trigger.
	if (Recoil > 0.05f)
	{
		if (APlayerController* PC = Cast<APlayerController>(GetController()))
		{
			PC->AddPitchInput(-Recoil * (bAiming ? 0.06f : 0.11f) * (bMoving ? 1.2f : 1.0f));
		}
	}
}

void AHopeCharacter::UpdateFocus(float DeltaSeconds)
{
	// One trace a frame down the sight line. The cine camera smooths the
	// change itself (FocusSmoothingInterpSpeed), so this can snap.
	const FVector Start = Camera->GetComponentLocation();
	const FVector End = Start + Camera->GetForwardVector() * TraceRange;

	FCollisionQueryParams Params;
	Params.AddIgnoredActor(this);

	FHitResult Hit;
	const float Distance = GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params)
		? Hit.Distance
		: 6000.0f;   // nothing downrange: hold focus at the far end of the block

	Camera->FocusSettings.ManualFocusDistance = FMath::Max(Distance, 60.0f);
}

void AHopeCharacter::FireOnce()
{
	--Ammo;
	Recoil = 1.0f;
	MuzzleTimer = 0.045f;

	const bool bMoving = GetVelocity().SizeSquared2D() > 400.0f;
	const float Spread = (bAiming ? SpreadAimed : SpreadHip) + (bMoving ? SpreadMoving : 0.0f);

	const FVector Start = Camera->GetComponentLocation();
	const FVector Dir = FMath::VRandCone(Camera->GetForwardVector(), FMath::DegreesToRadians(Spread));
	const FVector End = Start + Dir * TraceRange;

	FCollisionQueryParams Params;
	Params.AddIgnoredActor(this);

	FHitResult Hit;
	if (GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params))
	{
		if (AHopeShadow* Shadow = Cast<AHopeShadow>(Hit.GetActor()))
		{
			// Headshots are worth triple, as in the WebGL build. The head is
			// the top 26cm of the silhouette.
			const float HeadZ = Shadow->GetActorLocation().Z + Shadow->GetHeadHeightOffset();
			const bool bHead = Hit.ImpactPoint.Z > HeadZ;
			Shadow->TakeShadowDamage(bHead ? 3.0f : 1.0f, bHead);
		}
	}
}

bool AHopeCharacter::ApplyShadowHit(float Amount)
{
	if (!bAlive)
	{
		return false;
	}
	Health -= Amount;
	if (Health <= 0.0f)
	{
		Health = 0.0f;
		bAlive = false;
		bFiring = false;
		return true;
	}
	return false;
}

void AHopeCharacter::GiveAmmo(int32 Rounds)
{
	Reserve += Rounds;
}

void AHopeCharacter::Heal(float Amount)
{
	Health = FMath::Min(MaxHealth, Health + Amount);
}
