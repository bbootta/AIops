#include "HopeShadow.h"

#include "HopeBlocks.h"
#include "HopeCharacter.h"
#include "HopeGameMode.h"

#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
	constexpr float ContactRange = 150.0f;
	constexpr float AttackInterval = 1.05f;
}

AHopeShadow::AHopeShadow()
{
	PrimaryActorTick.bCanEverTick = true;

	Capsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Capsule"));
	Capsule->InitCapsuleSize(34.0f, 118.0f);
	// Blocks the shot trace and nothing else — shadows walk through each other
	// and through the player rather than jamming in the street.
	Capsule->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Capsule->SetCollisionResponseToAllChannels(ECR_Ignore);
	Capsule->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
	SetRootComponent(Capsule);

	Body = CreateDefaultSubobject<USceneComponent>(TEXT("Body"));
	Body->SetupAttachment(Capsule);
}

void AHopeShadow::BeginPlay()
{
	Super::BeginPlay();
	BuildSilhouette();
}

float AHopeShadow::GetHeadHeightOffset() const
{
	return Height * 0.5f - 26.0f;
}

USceneComponent* AHopeShadow::AddLimb(const FVector& Offset, const FVector& Size)
{
	USceneComponent* Pivot = NewObject<USceneComponent>(this);
	Pivot->SetupAttachment(Body);
	Pivot->RegisterComponent();
	Pivot->AttachToComponent(Body, FAttachmentTransformRules::KeepRelativeTransform);
	Pivot->SetRelativeLocation(Offset);

	UMaterialInterface* Ink = HopeBlocks::MaterialFor(
		this, TEXT("Shadow"), FLinearColor(0.006f, 0.005f, 0.010f), 0.98f);

	// Hung below the pivot, so rotating the pivot swings the limb.
	UStaticMeshComponent* Mesh = HopeBlocks::AddBox(
		this, Pivot, Size, FVector(0.0f, 0.0f, -Size.Z * 0.5f), FRotator::ZeroRotator, Ink);

	if (Mesh)
	{
		if (UMaterialInstanceDynamic* Dyn = Cast<UMaterialInstanceDynamic>(Mesh->GetMaterial(0)))
		{
			Skins.Add(Dyn);
		}
	}
	return Pivot;
}

void AHopeShadow::BuildSilhouette()
{
	const float H = Height;
	Body->SetRelativeLocation(FVector::ZeroVector);

	UMaterialInterface* Ink = HopeBlocks::MaterialFor(
		this, TEXT("Shadow"), FLinearColor(0.006f, 0.005f, 0.010f), 0.98f);

	// Torso and head, elongated — the creature reads as too tall for a person.
	if (UStaticMeshComponent* Torso = HopeBlocks::AddBox(this, Body,
		FVector(26.0f, 40.0f, H * 0.40f), FVector(0.0f, 0.0f, H * 0.16f), FRotator::ZeroRotator, Ink))
	{
		if (UMaterialInstanceDynamic* Dyn = Cast<UMaterialInstanceDynamic>(Torso->GetMaterial(0)))
		{
			Skins.Add(Dyn);
		}
	}
	if (UStaticMeshComponent* Head = HopeBlocks::AddBox(this, Body,
		FVector(22.0f, 24.0f, 30.0f), FVector(2.0f, 0.0f, H * 0.42f), FRotator::ZeroRotator, Ink))
	{
		if (UMaterialInstanceDynamic* Dyn = Cast<UMaterialInstanceDynamic>(Head->GetMaterial(0)))
		{
			Skins.Add(Dyn);
		}
	}

	const float LegLen = H * 0.42f;
	const float ArmLen = H * 0.38f;
	LeftLeg  = AddLimb(FVector(0.0f, -13.0f, -H * 0.06f), FVector(15.0f, 15.0f, LegLen));
	RightLeg = AddLimb(FVector(0.0f,  13.0f, -H * 0.06f), FVector(15.0f, 15.0f, LegLen));
	LeftArm  = AddLimb(FVector(0.0f, -26.0f,  H * 0.33f), FVector(13.0f, 13.0f, ArmLen));
	RightArm = AddLimb(FVector(0.0f,  26.0f,  H * 0.33f), FVector(13.0f, 13.0f, ArmLen));
}

void AHopeShadow::Configure(int32 Wave, bool bInBrute)
{
	bBrute = bInBrute;

	// Ported from the WebGL build: health scales every other wave, speed every
	// wave, and brutes trade speed for three times the health.
	Health = static_cast<float>((3 + Wave / 2) * (bBrute ? 3 : 1));
	Speed = (155.0f + FMath::FRand() * 80.0f) * (1.0f + Wave * 0.065f) * (bBrute ? 0.62f : 1.0f);
	Height = bBrute ? 310.0f : 235.0f;

	Capsule->SetCapsuleSize(bBrute ? 44.0f : 34.0f, Height * 0.5f);
	SetActorScale3D(FVector(1.0f));
}

void AHopeShadow::TakeShadowDamage(float Amount, bool bHeadshot)
{
	if (State != EShadowState::Walk)
	{
		return;
	}

	Health -= Amount;
	HitFlash = 0.14f;

	if (Health <= 0.0f)
	{
		State = EShadowState::Dying;
		DyingTimer = 0.85f;
		Capsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);

		if (AHopeGameMode* GM = GetWorld()->GetAuthGameMode<AHopeGameMode>())
		{
			GM->OnShadowKilled(this, bHeadshot);
		}
	}
}

void AHopeShadow::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Hit flash: the creature glows a bruised purple from inside for a moment.
	HitFlash = FMath::Max(0.0f, HitFlash - DeltaSeconds);
	const float Glow = HitFlash / 0.14f;
	for (UMaterialInstanceDynamic* Skin : Skins)
	{
		if (Skin)
		{
			Skin->SetVectorParameterValue(TEXT("EmissiveTint"),
				FLinearColor(0.36f * Glow, 0.20f * Glow, 0.62f * Glow));
			Skin->SetScalarParameterValue(TEXT("EmissiveStrength"), Glow * 5.0f);
		}
	}

	if (State == EShadowState::Dying)
	{
		DyingTimer -= DeltaSeconds;
		// Sinks and shrinks into the road rather than ragdolling.
		const float T = FMath::Clamp(DyingTimer / 0.85f, 0.0f, 1.0f);
		Body->SetRelativeScale3D(FVector(T, T, FMath::Max(0.05f, T * T)));
		AddActorLocalOffset(FVector(0.0f, 0.0f, -DeltaSeconds * 60.0f));
		if (DyingTimer <= 0.0f)
		{
			Destroy();
		}
		return;
	}

	AHopeCharacter* Player = Cast<AHopeCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));
	if (!Player || !Player->bAlive)
	{
		return;
	}

	FVector ToPlayer = Player->GetActorLocation() - GetActorLocation();
	ToPlayer.Z = 0.0f;
	const float Distance = ToPlayer.Size();
	if (Distance > KINDA_SMALL_NUMBER)
	{
		ToPlayer /= Distance;
	}

	SetActorRotation(FRotator(0.0f, ToPlayer.Rotation().Yaw, 0.0f));

	if (Distance > ContactRange)
	{
		AddActorWorldOffset(ToPlayer * Speed * DeltaSeconds, false);

		// Gait: legs counter-swing, arms trail. Cheap, but it stops the
		// silhouette from sliding, which is what gives it away as fake.
		GaitPhase += DeltaSeconds * (Speed / 55.0f);
		const float Swing = FMath::Sin(GaitPhase) * 32.0f;
		if (LeftLeg)  { LeftLeg->SetRelativeRotation(FRotator(Swing, 0.0f, 0.0f)); }
		if (RightLeg) { RightLeg->SetRelativeRotation(FRotator(-Swing, 0.0f, 0.0f)); }
		if (LeftArm)  { LeftArm->SetRelativeRotation(FRotator(-Swing * 0.7f - 18.0f, 0.0f, 0.0f)); }
		if (RightArm) { RightArm->SetRelativeRotation(FRotator(Swing * 0.7f - 18.0f, 0.0f, 0.0f)); }
	}
	else
	{
		AttackCooldown -= DeltaSeconds;
		if (AttackCooldown <= 0.0f)
		{
			AttackCooldown = AttackInterval;
			// Both arms come up on the strike.
			if (LeftArm)  { LeftArm->SetRelativeRotation(FRotator(-105.0f, 0.0f, 0.0f)); }
			if (RightArm) { RightArm->SetRelativeRotation(FRotator(-105.0f, 0.0f, 0.0f)); }

			if (Player->ApplyShadowHit(bBrute ? 22.0f : 12.0f))
			{
				if (AHopeGameMode* GM = GetWorld()->GetAuthGameMode<AHopeGameMode>())
				{
					GM->OnPlayerDied();
				}
			}
		}
	}
}
