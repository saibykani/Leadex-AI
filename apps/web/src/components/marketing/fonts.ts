import { Instrument_Serif } from "next/font/google";

/** Display serif for cinematic headlines only; body copy stays in the app's sans. */
export const serif = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], display: "swap" });
