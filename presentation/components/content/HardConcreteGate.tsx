import AutoFitMath from "@/components/content/AutoFitMath";
import Math from "@/components/content/Math";

interface HardConcreteGateProps {
  className?: string;
}

export default function HardConcreteGate({ className = "" }: HardConcreteGateProps) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-8 shadow-sm ${className}`}>
      <div className="text-base font-semibold text-slate-500">
        Stretch a gate beyond <Math tex="(0,1)" />, then clip back — creating point masses at exactly 0 and 1
      </div>

      {/* Track from gamma (<0) to zeta (>1), with the [0,1] clip window shaded. */}
      <div className="relative mt-10 mb-2 h-4">
        <div className="absolute inset-0 rounded-full bg-slate-200" />
        {/* clipped window [0,1] */}
        <div className="absolute inset-y-0 rounded-full bg-pe-teal/30" style={{ left: "12%", right: "12%" }} />
        {/* point mass at 0 (off) */}
        <div
          className="absolute top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full border-4 border-slate-400 bg-slate-100"
          style={{ left: "12%" }}
        />
        {/* point mass at 1 (on) */}
        <div
          className="absolute top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full border-4 border-pe-teal bg-pe-light"
          style={{ left: "88%" }}
        />
      </div>

      {/* boundary labels */}
      <div className="relative h-6 text-base font-bold text-pe-dark">
        <span className="absolute left-0 -translate-x-1/2">
          <Math tex="\gamma" />
        </span>
        <span className="absolute -translate-x-1/2" style={{ left: "12%" }}>
          0
        </span>
        <span className="absolute -translate-x-1/2" style={{ left: "88%" }}>
          1
        </span>
        <span className="absolute right-0 translate-x-1/2">
          <Math tex="\zeta" />
        </span>
      </div>

      <div className="mt-4 flex justify-between text-sm text-slate-500">
        <span>clip&nbsp;→&nbsp;0 · record dropped</span>
        <span>differentiable in between</span>
        <span>clip&nbsp;→&nbsp;1 · record kept</span>
      </div>

      <div className="mt-7 space-y-3 rounded-md bg-slate-50 px-5 py-4">
        <AutoFitMath>
          <Math display tex="z_i = \min\!\big(1,\ \max(0,\ \bar{s}_i)\big)" className="text-[1.15rem]" />
        </AutoFitMath>
        <AutoFitMath>
          <Math
            display
            tex="\Pr(z_i \neq 0) = \sigma\!\left(\log\alpha_i - \beta\log\tfrac{-\gamma}{\zeta}\right)"
            className="text-[1.15rem]"
          />
        </AutoFitMath>
      </div>
      <div className="mt-3 text-base leading-snug text-slate-500">
        The activation probability is differentiable, so the expected count can be penalized and trained
        by gradient descent.
      </div>
    </div>
  );
}
