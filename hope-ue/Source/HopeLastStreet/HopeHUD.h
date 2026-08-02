#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "HopeHUD.generated.h"

/**
 * Canvas-drawn HUD: reticle, ammunition, health and wave banner.
 *
 * Canvas rather than UMG on purpose — a UMG widget is a .uasset, and binary
 * assets cannot be authored outside the editor. This keeps the project
 * buildable from a clone. Rebuild it in UMG if you want it art-directed.
 */
UCLASS()
class HOPELASTSTREET_API AHopeHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
};
