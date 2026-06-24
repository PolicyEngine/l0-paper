import Slide from "@/components/core/Slide";
import { formatDate, SpeakerInfo } from "@/lib/types";

interface CoverSlideProps {
  title: string;
  subtitle: string;
  event: string;
  date: string;
  speakers: SpeakerInfo[];
}

export default function CoverSlide({
  title,
  subtitle,
  event,
  date,
  speakers,
}: CoverSlideProps) {
  return (
    <Slide isCover>
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-center text-center">
        <div className="mb-10 h-1 w-24 rounded-full bg-white/30" />
        <h1 className="max-w-5xl text-6xl font-extrabold leading-tight tracking-tight text-white">
          {title}
        </h1>
        <p className="mt-8 max-w-4xl text-2xl font-light leading-snug text-white/85">
          {subtitle}
        </p>
        <div className="mt-14 flex flex-wrap items-center justify-center gap-10">
          {speakers.map((speaker) => (
            <div key={speaker.name} className="text-center">
              <div className="mx-auto mb-3 flex h-20 w-20 items-center justify-center rounded-full border border-white/35 bg-white/10 text-2xl font-bold">
                {speaker.name
                  .split(" ")
                  .map((part) => part[0])
                  .join("")}
              </div>
              <div className="text-xl font-semibold">{speaker.name}</div>
              <div className="text-sm text-white/70">{speaker.title}</div>
            </div>
          ))}
        </div>
        <div className="mt-10 text-base font-medium text-white/70">
          {event} - {formatDate(date)}
        </div>
      </div>
    </Slide>
  );
}
