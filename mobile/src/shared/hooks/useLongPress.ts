import { useRef, useCallback } from 'react';

interface UseLongPressOptions {
  onLongPress: (e: React.MouseEvent | React.TouchEvent) => void;
  onClick?: (e: React.MouseEvent | React.TouchEvent) => void;
  delay?: number;
}

export const useLongPress = ({
  onLongPress,
  onClick,
  delay = 500,
}: UseLongPressOptions) => {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const targetRef = useRef<EventTarget | null>(null);

  const start = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      targetRef.current = e.target as EventTarget;
      timeoutRef.current = setTimeout(() => {
        onLongPress(e);
      }, delay);
    },
    [onLongPress, delay]
  );

  const clear = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      // If click was quick (not long press), trigger onClick
      if (onClick && e.target === targetRef.current) {
        onClick(e);
      }
      targetRef.current = null;
    },
    [onClick]
  );

  return {
    onMouseDown: start,
    onTouchStart: start,
    onMouseUp: clear,
    onMouseLeave: clear,
    onTouchEnd: clear,
  };
};
