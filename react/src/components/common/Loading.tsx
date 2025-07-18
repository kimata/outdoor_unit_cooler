import React from 'react';

interface LoadingProps {
  size?: 'small' | 'medium' | 'large';
  text?: string;
  className?: string;
}

const Loading = React.memo(({
  size = 'medium',
  text = 'Loading...',
  className = ''
}: LoadingProps) => {
  const sizeClasses = {
    small: 'display-6',
    medium: 'display-5',
    large: 'display-4'
  };

  return (
    <div className={`text-center ${className}`}>
      <span className={`align-middle ms-4 ${sizeClasses[size]}`}>
        {text}
      </span>
    </div>
  );
});

Loading.displayName = 'Loading';

export { Loading };
