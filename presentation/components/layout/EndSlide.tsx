import Slide from "@/components/core/Slide";

export default function EndSlide() {
  return (
    <Slide isEnd>
      <div className="mx-auto max-w-5xl text-center">
        <div className="mb-10 h-1 w-24 rounded-full bg-white/30" />
        <h1 className="text-7xl font-extrabold tracking-tight text-white">Questions</h1>
        <p className="mt-8 text-2xl font-light text-white/80">
          L0 regularization for subnational microsimulation calibration
        </p>
      </div>
    </Slide>
  );
}
