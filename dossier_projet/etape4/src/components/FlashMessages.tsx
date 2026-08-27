import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';
import { useAuth } from '../auth';

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const colorMap = {
  success: 'bg-green-50 text-green-700 border-green-200',
  error: 'bg-red-50 text-red-700 border-red-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
};

export function FlashMessages() {
  const { flashMessages, dismissFlash } = useAuth();

  if (flashMessages.length === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed top-20 right-4 z-50 flex flex-col gap-2 max-w-sm"
    >
      {flashMessages.map((msg) => {
        const Icon = iconMap[msg.type];
        return (
          <div
            key={msg.id}
            className={`flex items-center gap-2 px-4 py-3 rounded-2xl border ${colorMap[msg.type]} shadow-soft animate-fade-in`}
          >
            <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
            <span className="text-sm font-medium flex-1">{msg.text}</span>
            <button
              onClick={() => dismissFlash(msg.id)}
              className="flex-shrink-0 opacity-60 hover:opacity-100"
              aria-label="Fermer le message"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
