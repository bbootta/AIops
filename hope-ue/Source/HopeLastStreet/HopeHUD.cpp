#include "HopeHUD.h"

#include "HopeCharacter.h"
#include "HopeGameMode.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	const FLinearColor Ink(0.91f, 0.89f, 0.85f, 0.92f);
	const FLinearColor Warn(0.88f, 0.33f, 0.23f, 0.95f);
	const FLinearColor Dim(0.91f, 0.89f, 0.85f, 0.35f);
}

void AHopeHUD::DrawHUD()
{
	Super::DrawHUD();

	if (!Canvas)
	{
		return;
	}

	AHopeCharacter* Player = Cast<AHopeCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));
	AHopeGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<AHopeGameMode>() : nullptr;
	if (!Player || !GM)
	{
		return;
	}

	const float W = Canvas->SizeX;
	const float H = Canvas->SizeY;
	const float CX = W * 0.5f;
	const float CY = H * 0.5f;
	UFont* Big = GEngine->GetLargeFont();
	UFont* Small = GEngine->GetMediumFont();

	// Reticle: four ticks that open up as accuracy drops, so the spread the
	// trace actually uses is legible rather than hidden.
	if (Player->bAlive)
	{
		const float Gap = Player->bAiming ? 7.0f : 15.0f;
		const float Len = 9.0f;
		const FLinearColor C = Player->bAiming ? Ink : Dim;
		DrawLine(CX - Gap - Len, CY, CX - Gap, CY, C, 1.6f);
		DrawLine(CX + Gap, CY, CX + Gap + Len, CY, C, 1.6f);
		DrawLine(CX, CY - Gap - Len, CX, CY - Gap, C, 1.6f);
		DrawLine(CX, CY + Gap, CX, CY + Gap + Len, C, 1.6f);
	}

	// Health, bottom left.
	const float BarW = 260.0f;
	const float BarY = H - 62.0f;
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.45f), 42.0f, BarY, BarW, 10.0f);
	const float Frac = FMath::Clamp(Player->Health / AHopeCharacter::MaxHealth, 0.0f, 1.0f);
	DrawRect(Frac < 0.3f ? Warn : Ink, 42.0f, BarY, BarW * Frac, 10.0f);
	DrawText(TEXT("HP"), Dim, 42.0f, BarY - 20.0f, Small, 1.0f, false);

	// Ammunition, bottom right.
	const FString AmmoText = FString::Printf(TEXT("%d"), Player->Ammo);
	const FString ReserveText = FString::Printf(TEXT("/ %d"), Player->Reserve);
	DrawText(AmmoText, Player->Ammo == 0 ? Warn : Ink, W - 190.0f, BarY - 26.0f, Big, 1.6f, false);
	DrawText(ReserveText, Dim, W - 118.0f, BarY - 6.0f, Small, 1.0f, false);

	if (Player->bReloading)
	{
		DrawText(TEXT("RELOADING"), Ink, CX - 52.0f, CY + 54.0f, Small, 1.1f, false);
	}
	else if (Player->Ammo <= 6 && Player->Reserve > 0)
	{
		DrawText(TEXT("[R] RELOAD"), Warn, CX - 54.0f, CY + 54.0f, Small, 1.1f, false);
	}

	// Wave and score, top left.
	DrawText(FString::Printf(TEXT("WAVE %d"), GM->Wave), Ink, 42.0f, 38.0f, Big, 1.1f, false);
	DrawText(FString::Printf(TEXT("SCORE %d   KILLS %d"), GM->Score, GM->Kills),
		Dim, 42.0f, 66.0f, Small, 1.0f, false);

	// The dim goes down first, or it would paint over the banner it frames.
	if (GM->bGameOver)
	{
		DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), 0.0f, 0.0f, W, H);
	}

	if (GM->BannerTimer > 0.0f && !GM->Banner.IsEmpty())
	{
		const float Alpha = GM->bGameOver ? 1.0f : FMath::Clamp(GM->BannerTimer / 0.6f, 0.0f, 1.0f);
		DrawText(GM->Banner, FLinearColor(Ink.R, Ink.G, Ink.B, Alpha),
			CX - GM->Banner.Len() * 11.0f, H * 0.30f, Big, 2.4f, false);
	}

	if (GM->bGameOver)
	{
		DrawText(FString::Printf(TEXT("SCORE %d   KILLS %d   WAVE %d"), GM->Score, GM->Kills, GM->Wave),
			Ink, CX - 190.0f, H * 0.30f + 68.0f, Big, 1.2f, false);
		DrawText(TEXT("[SPACE] REDEPLOY"), Dim, CX - 92.0f, H * 0.30f + 104.0f, Small, 1.2f, false);
	}
}
