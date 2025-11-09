import type React from "react";
import { forwardRef } from "react";
import SvgDouyin from "./Douyin";

export const DouyinIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgDouyin ref={ref} {...props} />;
});