import Slide from "@/components/core/Slide";
import Image from "@/components/core/BasePathImage";

export default function EndSlide() {
  return (
    <Slide isEnd>
      <div className="relative z-10 flex h-full flex-col items-center justify-center space-y-9 text-center">
        <Image
          alt="PolicyEngine"
          className="opacity-100"
          height={100}
          priority
          src="/logos/white.svg"
          style={{ height: "auto" }}
          width={350}
        />

        <div className="h-1 w-20 rounded-full bg-white/30" />

        <h1 className="font-display text-7xl font-bold leading-tight text-white">
          Questions
        </h1>

        <p className="max-w-4xl text-center text-2xl leading-relaxed text-white/80">
          L0 regularization for subnational microsimulation calibration
        </p>
      </div>
    </Slide>
  );
}
