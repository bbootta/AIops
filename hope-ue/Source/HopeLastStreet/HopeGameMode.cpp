#include "HopeGameMode.h"

#include "HopeCharacter.h"
#include "HopeHUD.h"
#include "HopeShadow.h"
#include "HopeStreet.h"

#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	constexpr int32 MaxAliveShadows = 9;
}

AHopeGameMode::AHopeGameMode()
{
	PrimaryActorTick.bCanEverTick = true;

	DefaultPawnClass = AHopeCharacter::StaticClass();
	HUDClass = AHopeHUD::StaticClass();
	Rng.Initialize(20240721);
}

void AHopeGameMode::BeginPlay()
{
	Super::BeginPlay();

	// The level asset can be empty — the street builds itself here. That keeps
	// the project runnable from a clone, with no .uasset content to generate.
	Street = GetWorld()->SpawnActor<AHopeStreet>(
		AHopeStreet::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);

	// No PlayerStart in an empty level, so place the officer at the mouth of
	// the street looking down the block.
	if (APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		Pawn->SetActorLocation(FVector(0.0f, 0.0f, 140.0f));
		if (AController* C = Pawn->GetController())
		{
			C->SetControlRotation(FRotator(-4.0f, 0.0f, 0.0f));
		}
	}

	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		PC->bShowMouseCursor = false;
		PC->SetInputMode(FInputModeGameOnly());
	}

	StartNextWave();
}

void AHopeGameMode::StartNextWave()
{
	++Wave;
	Pending = 4 + Wave * 2;
	SpawnTimer = 0.0f;
	Banner = FString::Printf(TEXT("WAVE %d"), Wave);
	BannerTimer = 2.2f;
}

void AHopeGameMode::SpawnShadow()
{
	// They come out of the haze at the far end of the block, spread across its
	// width, never closer than the fog can hide them.
	const float X = Rng.FRandRange(6000.0f, AHopeStreet::StreetLength * 100.0f);
	const float Y = Rng.FRandRange(-560.0f, 560.0f);

	AHopeShadow* Shadow = GetWorld()->SpawnActor<AHopeShadow>(
		AHopeShadow::StaticClass(), FVector(X, Y, 140.0f), FRotator::ZeroRotator);

	if (Shadow)
	{
		const bool bBrute = Wave >= 3 && Rng.FRand() < 0.2f;
		Shadow->Configure(Wave, bBrute);
		Living.Add(Shadow);
	}
}

void AHopeGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	BannerTimer = FMath::Max(0.0f, BannerTimer - DeltaSeconds);

	if (bGameOver)
	{
		return;
	}

	Living.RemoveAll([](const TObjectPtr<AHopeShadow>& S)
	{
		AHopeShadow* Raw = S.Get();
		return !IsValid(Raw) || !Raw->IsAlive();
	});

	if (Pending > 0)
	{
		SpawnTimer -= DeltaSeconds;
		if (SpawnTimer <= 0.0f && Living.Num() < MaxAliveShadows)
		{
			SpawnShadow();
			--Pending;
			SpawnTimer = 1.1f + Rng.FRand() * 1.3f;
		}
	}
	else if (Living.Num() == 0)
	{
		// Wave cleared: resupply, as in the WebGL build.
		if (AHopeCharacter* Player = Cast<AHopeCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0)))
		{
			Player->GiveAmmo(60);
		}
		StartNextWave();
	}
}

void AHopeGameMode::OnShadowKilled(AHopeShadow* Shadow, bool bHeadshot)
{
	if (!Shadow)
	{
		return;
	}

	++Kills;
	Score += (Shadow->IsBrute() ? 250 : 100) + (bHeadshot ? 50 : 0);

	// Drop rates carried over: roughly a third drop ammunition, a sixth a
	// field dressing. Granted directly rather than dropped as a pickup actor,
	// because the shadows die where the player is already shooting.
	AHopeCharacter* Player = Cast<AHopeCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));
	if (!Player)
	{
		return;
	}

	const float Roll = Rng.FRand();
	if (Roll < 0.34f)
	{
		Player->GiveAmmo(30);
	}
	else if (Roll < 0.50f)
	{
		Player->Heal(30.0f);
	}
}

void AHopeGameMode::OnPlayerDied()
{
	bGameOver = true;
	// ASCII deliberately: the HUD draws with the engine's default font, which
	// has no hangul coverage. Korean HUD text needs a font asset — see README.
	Banner = TEXT("OVERRUN");
	BannerTimer = 9999.0f;
}

void AHopeGameMode::RequestRestart()
{
	if (!bGameOver)
	{
		return;
	}
	UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this, true)));
}
