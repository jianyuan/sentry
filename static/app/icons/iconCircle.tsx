import type {SVGIconProps} from './svgIcon';
import {SvgIcon} from './svgIcon';

/**
 * @deprecated This icon will be removed in new UI.
 */
function IconCircle(props: SVGIconProps) {
  return (
    <SvgIcon {...props} kind="path">
      <path d="M8,16a8,8,0,1,1,8-8A8,8,0,0,1,8,16ZM8,1.53A6.47,6.47,0,1,0,14.47,8,6.47,6.47,0,0,0,8,1.53Z" />
    </SvgIcon>
  );
}

IconCircle.displayName = 'IconCircle';

export {IconCircle};
