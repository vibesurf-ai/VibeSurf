import type React from "react";
import { forwardRef } from "react";
import SvgDouyin from "./douyin-icon.svg?react";

export const DouyinIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgDouyin ref={ref} {...props} />;
});