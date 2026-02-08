import React, { useState, useRef, useEffect } from 'react';

interface MBTISlidersProps {
  values: {
    ei: number; // 0-100, 0=I, 100=E
    sn: number; // 0-100, 0=S, 100=N
    tf: number; // 0-100, 0=T, 100=F
    jp: number; // 0-100, 0=J, 100=P
  };
  onChange: (dimension: 'ei' | 'sn' | 'tf' | 'jp', value: number) => void;
}

export const MBTISliders: React.FC<MBTISlidersProps> = ({ values, onChange }) => {
  const getMBTIType = () => {
    const ei = values.ei >= 50 ? 'E' : 'I';
    const sn = values.sn >= 50 ? 'N' : 'S';
    const tf = values.tf >= 50 ? 'F' : 'T';
    const jp = values.jp >= 50 ? 'P' : 'J';
    return `${ei}${sn}${tf}${jp}`;
  };

  const Slider = ({ 
    dimension, 
    leftLabel, 
    rightLabel, 
    value 
  }: { 
    dimension: 'ei' | 'sn' | 'tf' | 'jp';
    leftLabel: string;
    rightLabel: string;
    value: number;
  }) => {
    const [localValue, setLocalValue] = useState(value);
    const sliderRef = useRef<HTMLInputElement>(null);
    const isDragging = useRef(false);

    // Sync local value when prop changes (but not while dragging)
    useEffect(() => {
      if (!isDragging.current && sliderRef.current) {
        const newValue = value;
        setLocalValue(newValue);
        sliderRef.current.value = newValue.toString();
      }
    }, [value]);

    const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = parseInt(e.target.value);
      
      // Update local state immediately for smooth UI display
      setLocalValue(newValue);
      
      // DON'T update parent during dragging - only update on mouse up
      // This prevents React re-renders from interfering with native drag behavior
    };

    const handleMouseDown = () => {
      isDragging.current = true;
    };

    const handleMouseUp = () => {
      // Final sync on release - update parent state only when drag ends
      if (sliderRef.current) {
        const finalValue = parseInt(sliderRef.current.value);
        setLocalValue(finalValue);
        onChange(dimension, finalValue);
      }
      // Reset dragging flag after a short delay to allow state to sync
      setTimeout(() => {
        isDragging.current = false;
      }, 100);
    };

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-700 uppercase">{leftLabel}</span>
          <span className="text-xs font-bold text-slate-700 uppercase">{rightLabel}</span>
        </div>
        <div className="relative">
          <input
            ref={sliderRef}
            type="range"
            min="0"
            max="100"
            step="1"
            value={localValue}
            onChange={handleInput}
            onMouseDown={handleMouseDown}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onTouchStart={handleMouseDown}
            onTouchEnd={handleMouseUp}
            className="w-full h-3 rounded-lg appearance-none cursor-pointer slider touch-none"
            style={{
              background: `linear-gradient(to right, #475569 0%, #475569 ${localValue}%, #cbd5e1 ${localValue}%, #cbd5e1 100%)`
            }}
          />
        </div>
        <div className="flex items-center justify-center">
          <span className="text-xs font-mono text-slate-500">{localValue < 50 ? leftLabel.charAt(0) : rightLabel.charAt(0)}</span>
          <span className="text-xs font-mono text-slate-400 mx-2">({localValue})</span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <Slider
        dimension="ei"
        leftLabel="Introvert"
        rightLabel="Extrovert"
        value={values.ei}
      />
      <Slider
        dimension="sn"
        leftLabel="Sensing"
        rightLabel="Intuitive"
        value={values.sn}
      />
      <Slider
        dimension="tf"
        leftLabel="Thinking"
        rightLabel="Feeling"
        value={values.tf}
      />
      <Slider
        dimension="jp"
        leftLabel="Judging"
        rightLabel="Perceiving"
        value={values.jp}
      />
      
      {/* Display MBTI Type */}
      <div className="bg-indigo-50 border-2 border-indigo-200 p-3 text-center">
        <p className="text-xs font-bold text-slate-600 uppercase mb-1">Your MBTI Type</p>
        <p className="text-2xl font-black text-indigo-900 font-mono">{getMBTIType()}</p>
      </div>
    </div>
  );
};
