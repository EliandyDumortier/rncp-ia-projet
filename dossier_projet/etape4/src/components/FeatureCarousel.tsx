import { Search, Sparkles, Star, ShieldCheck, ChevronLeft, ChevronRight, Play } from 'lucide-react';
import type { CarouselSlide } from '../types';

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Search,
  Sparkles,
  Star,
  ShieldCheck,
};

interface FeatureCarouselProps {
  slides: CarouselSlide[];
  index: number;
  onNext: () => void;
  onPrev: () => void;
  onGoTo: (i: number) => void;
  onCtaClick: () => void;
}

export function FeatureCarousel({ slides, index, onNext, onPrev, onGoTo, onCtaClick }: FeatureCarouselProps) {
  const slide = slides[index];
  const Icon = iconMap[slide.icon];

  return (
    <section
      aria-label="Présentation de l'application"
      className="relative min-h-[440px] flex items-center overflow-hidden"
    >
      <img
        src={slide.image}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 w-full h-full object-cover transition-all duration-700"
      />
      <div className={`absolute inset-0 bg-gradient-to-br ${slide.gradient} opacity-80 mix-blend-multiply transition-all duration-700`} />
      <div className="absolute inset-0 bg-black/30" />

      <div className="relative max-w-6xl mx-auto px-4 sm:px-6 py-16 w-full">
        <div className="max-w-2xl">
          <span className="inline-flex items-center gap-2 bg-white/20 backdrop-blur-sm text-white text-sm font-medium px-4 py-1.5 rounded-full mb-5">
            <Sparkles className="w-4 h-4" aria-hidden="true" /> Étape 4 — Application IA
          </span>

          <div key={slide.id} className="animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                <Icon className="w-6 h-6 text-white" aria-hidden="true" />
              </div>
              <h1 className="font-display text-3xl sm:text-4xl font-bold text-white">
                {slide.title}
              </h1>
            </div>
            <p className="text-white/90 text-base sm:text-lg leading-relaxed mb-8 max-w-xl">
              {slide.description}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onPrev}
              className="w-10 h-10 rounded-full bg-white/20 hover:bg-white/30 backdrop-blur-sm flex items-center justify-center text-white transition-all"
              aria-label="Slide précédent"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="flex gap-2">
              {slides.map((_, i) => (
                <button
                  key={i}
                  onClick={() => onGoTo(i)}
                  className={`h-2 rounded-full transition-all ${i === index ? 'w-8 bg-white' : 'w-2 bg-white/40'}`}
                  aria-label={`Slide ${i + 1}`}
                />
              ))}
            </div>
            <button
              onClick={onNext}
              className="w-10 h-10 rounded-full bg-white/20 hover:bg-white/30 backdrop-blur-sm flex items-center justify-center text-white transition-all"
              aria-label="Slide suivant"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          <div className="flex items-center gap-3 flex-wrap mt-8">
            <button
              className="bg-white text-rose-600 hover:bg-rose-50 font-semibold px-6 py-2.5 rounded-2xl transition-all flex items-center gap-2 shadow-soft"
              onClick={onCtaClick}
            >
              <Play className="w-4 h-4" aria-hidden="true" /> Voir les recommandations
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
