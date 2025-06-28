import React, { useEffect, useState } from 'react';
import { motion, useSpring, useTransform } from 'framer-motion';

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  className?: string;
  duration?: number;
}

export const AnimatedNumber: React.FC<AnimatedNumberProps> = ({
  value,
  decimals = 1,
  className = '',
  duration = 10.0
}) => {
  const [displayValue, setDisplayValue] = useState(value);
  const spring = useSpring(value, {
    duration: duration * 1000,
    bounce: 0.1
  });

  const display = useTransform(spring, (latest) => latest.toFixed(decimals));

  useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  useEffect(() => {
    const unsubscribe = display.on('change', (latest) => {
      setDisplayValue(parseFloat(latest));
    });
    return unsubscribe;
  }, [display]);

  return (
    <motion.span
      className={className}
      initial={{ scale: 1 }}
      animate={{ scale: value !== displayValue ? [1, 1.05, 1] : 1 }}
      transition={{ duration: 0.3 }}
    >
      {display.get()}
    </motion.span>
  );
};
