import type React from "react";
import { forwardRef } from "react";
import { AIMLComponent } from "./AI-ML.jsx";

interface AIMLIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

export const AIMLIcon = forwardRef<SVGSVGElement, AIMLIconProps>(
  (props, ref) => {
    const { className = "", ...restProps } = props;
    return <AIMLComponent ref={ref} className={className} {...restProps} />;
  },
);
