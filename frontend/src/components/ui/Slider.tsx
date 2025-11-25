import * as React from 'react';
import { cn } from '@/lib/utils';

interface SliderProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  value?: number;
  min?: number;
  max?: number;
  step?: number;
  onValueChange?: (value: number) => void;
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, value = 0, min = 0, max = 100, step = 1, onValueChange, ...props }, ref) => {
    const percentage = ((value - min) / (max - min)) * 100;

    return (
      <div className={cn('relative w-full', className)}>
        <div className="absolute inset-0 h-2 rounded-full bg-muted my-auto" />
        <div
          className="absolute left-0 h-2 rounded-full bg-primary my-auto transition-all"
          style={{ width: `${percentage}%` }}
        />
        <input
          type="range"
          ref={ref}
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onValueChange?.(Number(e.target.value))}
          className="relative w-full h-2 appearance-none bg-transparent cursor-pointer z-10"
          {...props}
        />
      </div>
    );
  }
);

Slider.displayName = 'Slider';

export { Slider };
