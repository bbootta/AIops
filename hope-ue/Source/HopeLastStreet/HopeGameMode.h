#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "HopeGameMode.generated.h"

class AHopeShadow;
class AHopeStreet;

/**
 * Builds the street, then runs the wave director.
 *
 * Wave pacing, health and speed scaling, brute odds, scoring and drop rates
 * are all carried over unchanged from the WebGL build, so this plays the same
 * game with a different renderer under it.
 */
UCLASS()
class HOPELASTSTREET_API AHopeGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AHopeGameMode();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	void OnShadowKilled(AHopeShadow* Shadow, bool bHeadshot);
	void OnPlayerDied();

	/** Bound to Space on the game-over screen. */
	void RequestRestart();

	// Read by the HUD.
	int32 Wave = 0;
	int32 Score = 0;
	int32 Kills = 0;
	bool bGameOver = false;
	FString Banner;
	float BannerTimer = 0.0f;

private:
	void StartNextWave();
	void SpawnShadow();

	int32 Pending = 0;
	float SpawnTimer = 0.0f;
	FRandomStream Rng;

	UPROPERTY() TObjectPtr<AHopeStreet> Street;
	UPROPERTY() TArray<TObjectPtr<AHopeShadow>> Living;
};
